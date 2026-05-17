from django.urls import path
from EMSwebsite.controllers.settings_views import (
    settings, update_settings_ajax, get_settings_ajax,
    get_increment_settings, update_increment_settings,
)

urlpatterns = [
    path('settings/', settings, name='settings'),
    path('api/settings/update/', update_settings_ajax, name='update_settings_ajax'),
    path('api/settings/get/', get_settings_ajax, name='get_settings_ajax'),
    path('api/increment-settings/', get_increment_settings, name='get_increment_settings'),
    path('api/increment-settings/update/', update_increment_settings, name='update_increment_settings'),
]
