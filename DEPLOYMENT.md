# Deployment Instructions

## After deploying to Railway, run these commands:

1. **Apply the database migration** (adds logo field to Club model):
   ```bash
   python manage.py migrate
   ```

2. **Collect static files** (if needed):
   ```bash
   python manage.py collectstatic --noinput
   ```

## Important Notes:

- The `logo` field has been added to the Club model
- Migration file: `league/migrations/0004_club_logo.py`
- Pillow has been added to requirements.txt for image handling
- Media files will be served from `/media/` URL

## Testing the Approval Workflow:

1. Go to Django Admin → Team Registrations
2. Select one or more unapproved registrations
3. Choose "Approve selected registrations and create Clubs/Players" action
4. Upload logos (optional) for each team
5. Click "Approve and Create Clubs"
6. Teams will immediately appear on the ppl3hype page

## Media Files in Production:

- Uploaded logos are saved to `media/league/pplLogos/`
- Make sure your hosting service persists the `media/` directory
- For Railway, you may need to configure persistent storage or use cloud storage (S3, Cloudinary, etc.)
