web: daphne freelancer_hub.asgi:application --port $PORT --bind 0.0.0.0
worker: celery -A freelancer_hub worker --loglevel=info
beat: celery -A freelancer_hub beat --loglevel=info
