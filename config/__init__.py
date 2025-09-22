# config/__init__.py

# Importa nosso app Celery
from .celery import app as celery_app

__all__ = ('celery_app',)