# pretix order limits

This pretix plugin limits how many tickets from one event date may be included
in a single order. Limits are configured independently for every sales channel,
so the web shop can be restricted without limiting point-of-sale or API orders.

Enable the plugin for an event and open **Settings → Order limits**. The table
contains one row per event date and one column per sales channel. An empty field
means that the plugin imposes no limit for that combination. Add-on products are
not counted.

The regular pretix `max_items_per_order` setting still limits the total size of
the complete order across all dates. Raise that setting if an order should be
allowed to contain several full per-date allowances.

Limits are enforced by the cart and final-order validation hooks used by the
pretix storefront checkout. Direct order creation through the REST or Device API
does not run the storefront checkout and is intentionally unaffected.
