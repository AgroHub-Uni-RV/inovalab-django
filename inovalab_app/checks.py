from django.core.checks import Error, register
from django.core.exceptions import ImproperlyConfigured
from inovalab_app.adapters.host import get_adapter


@register()
def host_adapter_check(app_configs, **kwargs):
    try:
        get_adapter()
    except (ImportError, AttributeError, TypeError, ImproperlyConfigured) as error:
        return [Error(str(error), id='inovalab_app.E001')]
    return []
