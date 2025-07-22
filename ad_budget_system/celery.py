from __future__ import annotations

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ad_budget_system.settings")
app = Celery("ad_budget_system")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self, *args, **kwargs):
    print(f"Request: {self.request!r}")
