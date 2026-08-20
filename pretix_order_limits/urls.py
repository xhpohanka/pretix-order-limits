from django.urls import re_path

from .views import OrderLimitsSettings


urlpatterns = [
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/order-limits/settings$",
        OrderLimitsSettings.as_view(),
        name="settings",
    ),
]

