#!/bin/sh
set -eu

echo "[RideHub] Running Django checks"
python backend/manage.py check
echo "[RideHub] Applying database migrations"
python backend/manage.py migrate --noinput
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
