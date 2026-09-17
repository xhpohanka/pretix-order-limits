from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import (
    CartPosition, Event, Item, ItemCategory, Organizer, SalesChannel, SubEvent,
    Team, User,
)
from pretix.base.services.cart import CartError
from pretix.base.services.orders import OrderError
from pretix.testutils.sessions import get_cart_session_key

from pretix_order_limits.forms import OrderLimitsForm
from pretix_order_limits.limits import get_order_limit, setting_key
from pretix_order_limits.signals import (
    order_limits_settings_navigation, validate_cart_limits, validate_order_limits,
)


class OrderLimitTest(TestCase):
    @scopes_disabled()
    def setUp(self):
        self.organizer = Organizer.objects.create(name="Dummy", slug="dummy")
        self.event = Event.objects.create(
            organizer=self.organizer,
            name="Festival",
            slug="festival",
            date_from=now() + timedelta(days=30),
            has_subevents=True,
            live=True,
        )
        self.first = SubEvent.objects.create(
            event=self.event,
            name="First",
            date_from=now() + timedelta(days=30),
            active=True,
        )
        self.second = SubEvent.objects.create(
            event=self.event,
            name="Second",
            date_from=now() + timedelta(days=31),
            active=True,
        )
        self.category = ItemCategory.objects.create(event=self.event, name="Tickets")
        self.item = Item.objects.create(
            event=self.event,
            category=self.category,
            name="Ticket",
            default_price=Decimal("10.00"),
        )
        self.addon_category = ItemCategory.objects.create(event=self.event, name="Add-ons", is_addon=True)
        self.addon = Item.objects.create(
            event=self.event,
            category=self.addon_category,
            name="Add-on",
            default_price=Decimal("1.00"),
        )
        self.web = self.organizer.sales_channels.get(identifier="web")
        self.api = SalesChannel.objects.create(
            organizer=self.organizer,
            identifier="api.partner",
            label="Partner API",
            type="api",
        )
        self.event.plugins = "pretix_order_limits"
        self.event.save(update_fields=["plugins"])
        self.user = User.objects.create_user("staff@example.com", "password")
        team = Team.objects.create(organizer=self.organizer, name="Staff", all_event_permissions=True)
        team.all_events = True
        team.save()
        team.members.add(self.user)
        self.client.force_login(self.user)

    @scopes_disabled()
    def positions(self, *subevents, addon=False):
        positions = []
        for index, subevent in enumerate(subevents):
            base = CartPosition.objects.create(
                event=self.event,
                cart_id=f"cart-{len(positions)}-{index}",
                item=self.item,
                subevent=subevent,
                price=Decimal("10.00"),
                expires=now() + timedelta(minutes=10),
            )
            positions.append(base)
            if addon:
                positions.append(CartPosition.objects.create(
                    event=self.event,
                    cart_id=base.cart_id,
                    item=self.addon,
                    subevent=subevent,
                    addon_to=base,
                    price=Decimal("1.00"),
                    expires=base.expires,
                ))
        return positions

    @scopes_disabled()
    def test_limit_is_scoped_to_subevent_and_channel(self):
        self.event.settings.set(setting_key(self.web, self.first), 2)
        positions = self.positions(self.first, self.first, self.first)

        with self.assertRaises(CartError):
            validate_cart_limits(self.event, positions, sales_channel=self.web)
        validate_cart_limits(self.event, positions, sales_channel=self.api)

    @scopes_disabled()
    def test_positions_from_different_dates_are_counted_separately(self):
        self.event.settings.set(setting_key(self.web, self.first), 2)
        self.event.settings.set(setting_key(self.web, self.second), 2)
        positions = self.positions(self.first, self.first, self.second, self.second)

        validate_order_limits(self.event, positions, sales_channel=self.web)

    @scopes_disabled()
    def test_addons_are_not_counted(self):
        self.event.settings.set(setting_key(self.web, self.first), 1)
        positions = self.positions(self.first, addon=True)

        validate_cart_limits(self.event, positions, sales_channel=self.web)

    @scopes_disabled()
    def test_final_order_validation_uses_same_limit(self):
        self.event.settings.set(setting_key(self.api, self.first), 1)
        positions = self.positions(self.first, self.first)

        with self.assertRaises(OrderError):
            validate_order_limits(self.event, positions, sales_channel=self.api)

    def test_settings_are_in_event_navigation(self):
        response = self.client.get(
            f"/control/event/{self.organizer.slug}/{self.event.slug}/order-limits/settings"
        )

        links = order_limits_settings_navigation(self.event, response.wsgi_request)
        self.assertEqual(links[0]["label"], "Order limits")
        self.assertTrue(links[0]["active"])

    @scopes_disabled()
    def test_event_without_subevents_uses_event_scope(self):
        event = Event.objects.create(
            organizer=self.organizer,
            name="Conference",
            slug="conference",
            date_from=now() + timedelta(days=40),
        )
        item = Item.objects.create(event=event, name="Ticket", default_price=Decimal("10.00"))
        event.settings.set(setting_key(self.web), 1)
        positions = [
            CartPosition.objects.create(
                event=event,
                cart_id=f"plain-{index}",
                item=item,
                price=Decimal("10.00"),
                expires=now() + timedelta(minutes=10),
            )
            for index in range(2)
        ]

        with self.assertRaises(CartError):
            validate_cart_limits(event, positions, sales_channel=self.web)

    @scopes_disabled()
    def test_settings_form_saves_and_clears_limits(self):
        field = OrderLimitsForm.field_name(self.web, self.first)
        data = {}
        initial = OrderLimitsForm(event=self.event)
        for name in initial.fields:
            data[name] = ""
        data[field] = "3"

        form = OrderLimitsForm(data=data, event=self.event)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(get_order_limit(self.event, self.web, self.first), 3)

        data[field] = ""
        form = OrderLimitsForm(data=data, event=self.event)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertIsNone(get_order_limit(self.event, self.web, self.first))

    def test_settings_view_renders_and_saves_matrix(self):
        url = f"/control/event/{self.organizer.slug}/{self.event.slug}/order-limits/settings"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.web.identifier)
        self.assertContains(response, self.api.identifier)

        field = OrderLimitsForm.field_name(self.web, self.first)
        response = self.client.post(url, {field: "4"})
        self.assertRedirects(response, url)
        self.assertEqual(get_order_limit(self.event, self.web, self.first), 4)

    @scopes_disabled()
    def test_web_checkout_is_blocked_by_configured_channel_limit(self):
        self.event.settings.set(setting_key(self.web, self.first), 1)
        self.client.get(f"/{self.organizer.slug}/{self.event.slug}/")
        cart_id = get_cart_session_key(self.client, self.event)
        for index in range(2):
            CartPosition.objects.create(
                event=self.event,
                cart_id=cart_id,
                item=self.item,
                subevent=self.first,
                price=Decimal("10.00"),
                expires=now() + timedelta(minutes=10),
            )

        response = self.client.get(
            f"/{self.organizer.slug}/{self.event.slug}/checkout/start",
            follow=True,
        )

        self.assertContains(response, "at most 1 ticket")
