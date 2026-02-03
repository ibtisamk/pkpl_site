# PKPL Site

This is the Django project for the PKPL site.

Quick deploy notes (Railway):

- Ensure `SECRET_KEY` and other secrets are set in Railway environment variables.
- Set `DEBUG=False` in env and configure `ALLOWED_HOSTS` appropriately.
- Railway: add PostgreSQL plugin and set `DATABASE_URL`.
- Ensure `gunicorn` is in `requirements.txt` (it is already included).
- Create a `Procfile` with: `web: gunicorn pkpl_site.wsgi --log-file -`.
- Run migration and collectstatic after deploy:

```bash
railway run python manage.py migrate
railway run python manage.py collectstatic --noinput
```
# Pakistani Pro Clubs League — PPL Site (Django)

A full-featured league management platform built for the **Pakistani Pro Clubs League (FC 26 onwards)**.  
This project powers team registrations, fixtures, standings, player stats, and dynamic season pages — all built with Django.

## 🚀 Features
- Team registration system with validation
- Player registration + detailed player pages
- Dynamic fixtures, groups, and knockout stages
- Season-specific pages (PPL1, PPL2, PPL3)
- Admin tools for importing data and managing league content
- Clean UI templates for teams, players, and match details

## 🛠 Tech Stack
- **Python 3**
- **Django**
- **SQLite** (local development)
- **HTML / CSS / JS**
- **Bootstrap** (optional depending on your templates)

## 📦 Installation

```bash
git clone https://github.com/ibtisamk/pkpl_site.git
cd pkpl_site
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

## 👤 Author
**Ibtisam Khalid**  
Creator & Technical Lead for the Pakistani Pro Clubs League digital platform.

