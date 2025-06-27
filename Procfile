web: gunicorn freelancer_hub.wsgi --bind 0.0.0.0:$PORT --workers 4 --timeout 120 --access-logfile -
worker: celery -A freelancer_hub worker --loglevel=info --concurrency=4
beat: celery -A freelancer_hub beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
