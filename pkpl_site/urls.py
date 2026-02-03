"""
URL configuration for pkpl_site project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from league import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    ...
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


urlpatterns = [

    # -----------------------------------------------------
    # HOMEPAGE → PPL3 HYPE PAGE (PRE-LAUNCH)
    # -----------------------------------------------------
    path("", lambda request: redirect("ppl3hype"), name="home"),

    # -----------------------------------------------------
    # DJANGO ADMIN
    # -----------------------------------------------------
    path("admin/", admin.site.urls),

    # -----------------------------------------------------
    # STATIC PAGES / ARCHIVE
    # -----------------------------------------------------
    path("ppl3hype/", views.ppl3hype, name="ppl3hype"),
    path("story/", views.story, name="story"),
    path("ppl1/", views.ppl1, name="ppl1"),
    path("ppl2/", views.ppl2, name="ppl2"),
    path("teams/", views.teams, name="teams"),
    path("players/", views.all_players, name="all_players"),
    path("team/<int:club_id>/", views.team_detail, name="team_detail"),
    path("player/<int:player_id>/", views.player_detail, name="player_detail"),
    path("rankings/", views.rankings, name="rankings"),
    path("register/", views.register, name="register"),
    path("register/team/", views.register_team, name="register_team"),
    path("register/player/", views.register_player, name="register_player"),
    path("register/success/", views.register_success, name="register_success"),


    # -----------------------------------------------------
    # PPL3 DASHBOARD (BACKEND-POWERED)
    # -----------------------------------------------------
    path("ppl3/", views.ppl3, name="ppl3"),  # redirect → ppl3_overview
    path("ppl3/overview/", views.ppl3_overview, name="ppl3_overview"),
    path("ppl3/groups/", views.ppl3_groups, name="ppl3_groups"),
    path("ppl3/fixtures/", views.ppl3_fixtures, name="ppl3_fixtures"),
    path("ppl3/knockouts/", views.ppl3_knockouts, name="ppl3_knockouts"),
    path("ppl3/match/<int:match_id>/", views.ppl3_match_detail, name="ppl3_match_detail"),
    path("ppl3/team/<int:club_id>/", views.ppl3_team, name="ppl3_team"),
    path("ppl3/player/<int:player_id>/", views.ppl3_player, name="ppl3_player"),

    # Fixtures pages
    path("fixtures/upcoming/", views.upcoming_fixtures, name="upcoming_fixtures"),
    path("fixtures/results/", views.results, name="results"),
]



