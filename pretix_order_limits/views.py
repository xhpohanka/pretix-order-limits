from django.contrib import messages
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from pretix.control.permissions import EventPermissionRequiredMixin
from pretix.control.views.event import EventSettingsViewMixin

from .forms import OrderLimitsForm


class OrderLimitsSettings(EventSettingsViewMixin, EventPermissionRequiredMixin, FormView):
    template_name = "pretix_order_limits/settings.html"
    permission = "event.settings.general:write"
    form_class = OrderLimitsForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["channels"] = context["form"].channels
        context["limit_rows"] = context["form"].limit_rows()
        return context

    def get_success_url(self):
        return reverse("plugins:pretix_order_limits:settings", kwargs={
            "organizer": self.request.organizer.slug,
            "event": self.request.event.slug,
        })

    def form_valid(self, form):
        changed = form.save()
        if changed:
            self.request.event.log_action(
                "pretix_order_limits.changed",
                user=self.request.user,
                data={"limits": changed},
            )
            messages.success(self.request, _("The order limits have been saved."))
        else:
            messages.info(self.request, _("No settings were changed."))
        return super().form_valid(form)

