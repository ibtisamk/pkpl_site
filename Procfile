release: python manage.py migrate --no-input && python manage.py collectstatic --no-input && python manage.py rebuild_player_season_stats
web: gunicorn pkpl_site.wsgi:application --bind 0.0.0.0:${PORT:-8000} --log-file -
