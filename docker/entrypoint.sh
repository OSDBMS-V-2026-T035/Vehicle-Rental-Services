#!/bin/sh
set -eu

echo "[RideHub] Running Django checks"
python backend/manage.py check
echo "[RideHub] Applying database migrations"
python backend/manage.py migrate --noinput
if [ -n "${RIDEHUB_ADMIN_PASSWORD:-}" ]; then
    echo "[RideHub] Ensuring the protected administrator account exists without resetting its password"
    python backend/manage.py bootstrap_admin
fi
echo "[RideHub] Verifying database schema and authentication readiness"
python backend/manage.py verify_runtime
echo "[RideHub] Collecting static files"
python backend/manage.py collectstatic --noinput

if [ "${INSTALL_MYSQL_EXTENSIONS:-false}" = "true" ]; then
    python scripts/install_mysql_extensions.py
fi

exec gunicorn config.wsgi:application \
    --chdir backend \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout "${WEB_TIMEOUT:-120}" \
    --access-logfile - \
    --error-logfile -
