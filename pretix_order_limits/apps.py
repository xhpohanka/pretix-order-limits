from django.utils.translation import gettext_lazy as _

from pretix.base.plugins import PluginConfig

from . import __version__


class PluginApp(PluginConfig):
    name = "pretix_order_limits"
    verbose_name = _("Order limits")

    class PretixPluginMeta:
        name = _("Order limits")
        author = "Jan Pohanka"
        description = _("Limit order sizes by event date and sales channel.")
        category = "FEATURE"
        visible = True
        version = __version__
        compatibility = "pretix>=2026.7.0.dev0"
        settings_links = [
            ((_('Settings'), _('Order limits')), 'plugins:pretix_order_limits:settings', {}),
        ]

    def ready(self):
        from . import signals  # noqa: F401

