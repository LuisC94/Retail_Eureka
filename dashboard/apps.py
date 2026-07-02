from django.apps import AppConfig
import os

class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'

    def ready(self):
        if os.environ.get('RUN_MAIN') == 'true':
            from .sensor_sync import start_sensor_sync_thread
            start_sensor_sync_thread()
