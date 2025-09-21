# portal/apps.py

from django.apps import AppConfig

class PortalConfig(AppConfig):
    # Esta linha diz ao Django para usar 'AutoField' (int) em vez de 'BigAutoField' (bigint)
    # para as chaves primárias automáticas neste app.
    default_auto_field = 'django.db.models.AutoField'
    name = 'portal'