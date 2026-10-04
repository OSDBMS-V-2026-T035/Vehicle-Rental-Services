# Docker and free hosting plan

## What Docker provides

Docker packages the Django application, Gunicorn runtime, and MySQL 8.4 into reproducible containers. `compose.yaml` is for local development or a single public VM. `docker-compose.prod.yml` adds Nginx and keeps MySQL on an internal Docker network.

## Local run requirements

- Docker Desktop with Docker Compose v2
- At least 4 GB RAM available to Docker
- 10 GB free disk space for images, MySQL data, and media
- A `.env` file copied from `.env.example`
- Values for `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD`
- Optional `BREVO_API_KEY` and `GOOGLE_MAPS_API_KEY`

Run:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The first start builds the image, waits for MySQL's health check, applies Django migrations, collects static files, installs the reporting view/stored procedure, and starts Gunicorn. Stop it with `Ctrl+C`; data remains in Docker named volumes. Use `docker compose down -v` only when you intentionally want to delete the database and uploaded media volumes.

## Can Docker keep the website free forever?

No. Docker itself is free software, but it does not supply a permanent public server, domain, bandwidth, backups, or database hosting.

For a PBL demo, the most practical zero-cost choices are:

1. **Oracle Cloud Always Free VM:** run the production Compose stack on an Always Free AMD or Ampere VM. Oracle currently states that Always Free services are available for an unlimited time, but capacity is limited, accounts can be suspended for inactivity or policy violations, a card is required for identity verification, and service limits/availability can change. This is the closest fit for keeping MySQL 8.4 and Docker together.
2. **Render Free web service:** suitable for the Django container, but it sleeps after 15 minutes of inactivity, has 750 free instance hours/month, and has an ephemeral filesystem. Render's free Postgres expires after 30 days, so it is not a suitable permanent MySQL replacement for this project. A separate database would be needed.
3. **Local machine/tunnel:** free for a short mentor demo, but it is not reliable hosting because the PC, network, and tunnel must remain online.

There is no honest guarantee that any third-party free hosting remains free forever. Oracle's Always Free tier is the best current architecture for this MySQL requirement, while Render is easier for a stateless demo but has unsuitable free-database limitations.

## Public deployment requirements

- An Oracle Cloud account and an available Always Free VM, or another VPS
- SSH access to the VM
- A domain name (optional; the VM public IP can work for a demo)
- DNS A record if using a domain
- HTTPS certificate, preferably via Let's Encrypt
- Firewall rules allowing only SSH and HTTP/HTTPS
- Strong production `.env` values with `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` set to the public hostname
- A backup destination and a tested restore procedure
- Brevo credentials for real email OTP delivery
- A restricted Google Maps browser key if live autocomplete is required

The current repository contains the Docker packaging and production Compose files, but an actual public deployment still requires the hosting account, server credentials, DNS, and secrets. Those should be entered by the project owner rather than committed to Git.
