from collections import Counter

from django.dispatch import receiver
from django.utils.translation import ngettext

from pretix.base.services.cart import CartError
from pretix.base.services.orders import OrderError
from pretix.base.signals import validate_cart, validate_order

from .limits import get_order_limit


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
