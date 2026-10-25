"""Fast, isolated settings for the Django test suite.

Production and local development continue to use the configured MySQL database;
tests use a disposable SQLite database so running them does not require MySQL
CREATE DATABASE privileges or touch a developer database.
"""

from .settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# WhiteNoise is a deployment-only static-file middleware and is intentionally
# not required for isolated database/API tests.
MIDDLEWARE = [item for item in MIDDLEWARE if item != "whitenoise.middleware.WhiteNoiseMiddleware"]
