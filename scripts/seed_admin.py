"""Create the admin named by ADMIN_EMAIL and ADMIN_PASSWORD, unless that user already exists."""

from app.config import Settings
from app.core.database import make_sessions
from app.services import user_service

settings = Settings.from_env()
if not settings.admin_email or not settings.admin_password:
    print("ADMIN_EMAIL or ADMIN_PASSWORD is not set; no admin seeded")
else:
    with make_sessions(settings.database_url)() as db:
        created = user_service.seed_admin(db, settings.admin_email, settings.admin_password)
    print(f"Admin {settings.admin_email}: {'created' if created else 'already exists'}")
