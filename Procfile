release: python manage.py collectstatic --no-input
web: gunicorn pkpl_site.wsgi --log-file -
