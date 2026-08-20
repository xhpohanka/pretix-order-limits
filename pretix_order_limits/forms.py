from django import forms
from django.conf import settings
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _

from .limits import get_order_limit, setting_key


class OrderLimitsForm(forms.Form):
    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.channels = list(event.organizer.sales_channels.all())
        self.scopes = list(event.subevents.order_by("date_from", "pk")) if event.has_subevents else [None]
        self.rules = []

        for subevent in self.scopes:
            cells = []
            for channel in self.channels:
                name = self.field_name(channel, subevent)
                self.fields[name] = forms.IntegerField(
                    required=False,
                    min_value=1,
                    max_value=settings.PRETIX_MAX_ORDER_SIZE,
                    initial=get_order_limit(event, channel, subevent),
                    label=str(channel),
                )
                cells.append((channel, name))
            self.rules.append((subevent, cells))

    @staticmethod
    def field_name(channel, subevent):
        scope = subevent.pk if subevent is not None else "event"
        return f"limit_{channel.pk}_{scope}"

    def limit_rows(self):
        rows = []
        for subevent, cells in self.rules:
            rows.append({
                "label": (
                    date_format(subevent.date_from, "SHORT_DATETIME_FORMAT")
                    if subevent is not None else _("Event")
                ),
                "fields": [self[name] for channel, name in cells],
            })
        return rows

    def save(self):
        changed = {}
        for subevent, cells in self.rules:
            for channel, name in cells:
                previous = get_order_limit(self.event, channel, subevent)
                current = self.cleaned_data[name]
                if current == previous:
                    continue
                key = setting_key(channel, subevent)
                if current is None:
                    self.event.settings.delete(key)
                else:
                    self.event.settings.set(key, current)
                changed[key] = {"old": previous, "new": current}
        return changed

