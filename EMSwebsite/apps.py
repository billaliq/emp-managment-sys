from django.apps import AppConfig


class EMSwebsiteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'EMSwebsite'

    def ready(self):
        # Import only when Django is ready
        from .views.devices import start_sync_on_django_start
        start_sync_on_django_start()
        # Import signals to register them
        import EMSwebsite.signals