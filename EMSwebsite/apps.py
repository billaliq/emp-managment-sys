from django.apps import AppConfig


class EiswebsiteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'EISwebsite'

    def ready(self):
        # Import only when Django is ready
        from .views import start_sync_on_django_start
        start_sync_on_django_start()
        # Import signals to register them
        import EISwebsite.signals