web: gunicorn bloodcoord.wsgi --bind 0.0.0.0:$PORT --workers 2
release: python manage.py migrate --noinput
