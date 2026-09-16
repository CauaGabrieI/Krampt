web: python manage.py migrate --noinput && gunicorn krampt.wsgi:application --bind 0.0.0.0:${PORT:-8000} --access-logfile - --error-logfile -
worker: python manage.py process_outbox
