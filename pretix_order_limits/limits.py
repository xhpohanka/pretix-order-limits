SETTING_PREFIX = "order_limits_max_"


def setting_key(sales_channel, subevent=None):
    scope = subevent.pk if subevent is not None else "event"
    return f"{SETTING_PREFIX}{sales_channel.pk}_{scope}"


def get_order_limit(event, sales_channel, subevent=None):
    value = event.settings.get(setting_key(sales_channel, subevent), default=None)
    if value in (None, ""):
        return None
    value = int(value)
    return value if value > 0 else None

