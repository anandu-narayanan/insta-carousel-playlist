"""
Celery app configuration for carousel_app.
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carousel_app.settings')

app = Celery('carousel_app')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
