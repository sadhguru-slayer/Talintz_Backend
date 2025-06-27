web: python manage.py migrate && gunicorn freelancer_hub.wsgi --bind 0.0.0.0:$PORT --workers 3 --timeout 180
worker: celery -A freelancer_hub worker --loglevel=info
