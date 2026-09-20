from collections import Counter

from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from pretix.base.services.cart import CartError
from pretix.base.services.orders import OrderError
from pretix.base.signals import event_copy_data, validate_cart, validate_order
from pretix.control.signals import nav_event_settings

from .limits import SETTING_PREFIX, get_order_limit


@receiver(event_copy_data, dispatch_uid="pretix_order_limits_drop_copied_pk_settings")
def drop_copied_pk_settings(sender, other, **kwargs):
    """
    Event.copy_data_from() copies every setting verbatim. Our keys are
    ``order_limits_max_<sales channel>_<scope>``, where the scope is either a subevent id
    or the literal "event".

    Dates are not copied, so per-date limits would point at nothing - drop them. The
    event-wide ones are keyed on a sales channel, which belongs to the organizer rather
    than the event, so they survive a copy within the same organizer and only have to go
    when the copy crosses organizers.
    """
    crosses_organizers = sender.organizer_id != other.organizer_id
    for key in [s.key for s in sender.settings._objects.all() if s.key.startswith(SETTING_PREFIX)]:
        if crosses_organizers or key.rsplit("_", 1)[-1] != "event":
            sender.settings.delete(key)


@receiver(nav_event_settings, dispatch_uid="pretix_order_limits_nav_event_settings")
def order_limits_settings_navigation(sender, request, **kwargs):
    if not request.user.has_event_permission(
        request.organizer, request.event, "event.settings.general:write", request=request,
    ):
        return []
    return [{
        "label": _("Order limits"),
        "url": reverse("plugins:pretix_order_limits:settings", kwargs={
            "organizer": request.organizer.slug,
            "event": request.event.slug,
        }),
        "active": resolve(request.path_info).namespace == "plugins:pretix_order_limits",
    }]


def _limit_message(subevent, limit):
    if subevent is None:
        return ngettext(
            "You can order at most %(limit)s ticket for this event in a single order.",
            "You can order at most %(limit)s tickets for this event in a single order.",
            limit,
        ) % {"limit": limit}
    return ngettext(
        "You can order at most %(limit)s ticket for %(date)s in a single order.",
        "You can order at most %(limit)s tickets for %(date)s in a single order.",
        limit,
    ) % {"limit": limit, "date": str(subevent)}


def enforce_order_limits(event, positions, sales_channel, error_class):
    if sales_channel is None:
        return

    counts = Counter()
    subevents = {}
    for position in positions:
        if position.addon_to_id:
            continue
        counts[position.subevent_id] += 1
        subevents[position.subevent_id] = position.subevent if position.subevent_id is not None else None
    for subevent_id, count in counts.items():
        subevent = subevents[subevent_id]
        limit = get_order_limit(event, sales_channel, subevent)
        if limit is not None and count > limit:
            raise error_class(_limit_message(subevent, limit))


@receiver(validate_cart, dispatch_uid="pretix_order_limits_validate_cart")
def validate_cart_limits(sender, positions, sales_channel=None, **kwargs):
    enforce_order_limits(sender, positions, sales_channel, CartError)


@receiver(validate_order, dispatch_uid="pretix_order_limits_validate_order")
def validate_order_limits(sender, positions, sales_channel=None, **kwargs):
    enforce_order_limits(sender, positions, sales_channel, OrderError)
