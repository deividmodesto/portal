# config/celery.py
import os
from celery import Celery

# Define o módulo de configurações do Django para o Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Usa as configurações do Django (variáveis CELERY_...)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Carrega tarefas de todos os apps registrados no Django
app.autodiscover_tasks()