from django.apps import AppConfig
from django.apps import AppConfig

class LeagueConfig(AppConfig):
    name = 'league'

class LeagueConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'league'

    def ready(self):
        import league.signals
