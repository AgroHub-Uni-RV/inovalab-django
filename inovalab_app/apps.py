from django.apps import AppConfig


class InovalabConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inovalab_app'
    label = 'inovalab_app'
    verbose_name = 'InovaLab'

    def ready(self):
        from inovalab_app import checks  # noqa: F401
