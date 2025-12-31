# ~/ebi3/ebi3/celery.py

import os
from celery import Celery
from celery.schedules import crontab

# Définir les paramètres Django par défaut
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ebi3.settings')

app = Celery('ebi3')

# Configuration Celery à partir des paramètres Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Découverte automatique des tâches dans les apps
app.autodiscover_tasks()

# Configuration des tâches périodiques
from logistics.tasks import CELERY_BEAT_SCHEDULE
app.conf.beat_schedule = CELERY_BEAT_SCHEDULE

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')