# Vehicle Rental Services

Vehicle rental platform built with HTML, CSS, JavaScript, Python, Django, and MySQL 8.4.

## Technology stack

- **Frontend:** HTML, CSS, and vanilla JavaScript
- **Backend:** Python and Django
- **Database:** MySQL 8.4
- **Architecture:** Django project configuration with domain-focused apps and separate database artifacts, suitable for integrating operating-system and DBMS concepts.

## Project structure

```text
frontend/       Static frontend source files grouped by type
backend/        Django project and domain applications
  config/       Django settings, URL routing, ASGI, and WSGI entry points
  apps/         Domain-focused Django applications
  templates/    Shared Django templates and future backend views
  static/       Shared backend static assets
database/       Database schema, queries, and seed scripts
tests/          Cross-application and integration tests
docs/           Project documentation and design notes
```

The frontend landing page is in `frontend/html/index.html`, with its styles,
interactions, and vehicle imagery in `frontend/css/`, `frontend/js/`, and
`frontend/images/`. Django serves the page through the root URL. The first working
marketplace milestone is implemented in `accounts`, `shops`, `vehicles`,
`bookings`, and `adminpanel`; payments, verification integrations, and notifications
remain separate extension points.

## Marketplace workflow

- Customers can search approved vehicles and verified shops by global location.
- Shopkeepers sign up with email OTP and receive temporary access immediately.
- A pending shopkeeper can edit shop name/address, but cannot list vehicles.
- Admins review shopkeepers at `/control-panel/`, then approve, reject, or revoke access.
- Verified shopkeepers submit vehicle details and sample photos; each listing waits for admin approval.
- Approved listings include a Google Maps directions link when coordinates are available.
- Pickup dates cannot be in the past. Round-trip return dates are limited to seven days after pickup.

The detailed OS/DBMS mapping is in [`docs/OS_DBMS_IMPLEMENTATION.md`](docs/OS_DBMS_IMPLEMENTATION.md).

## Docker deployment

Docker files are included for local and VPS deployment:

```powershell
Copy-Item .env.example .env
# Set MYSQL_PASSWORD and MYSQL_ROOT_PASSWORD in .env
docker compose up --build
```

Open `http://localhost:8000/`. The Compose stack runs Django/Gunicorn and MySQL
8.4 with persistent named volumes. For a public server, use
`docker-compose.prod.yml` with the Nginx reverse proxy and HTTPS termination.
Docker is the packaging/runtime layer; it does not itself provide free public
hosting. See `docs/DEPLOYMENT.md` for the free-hosting trade-offs.

## Initial setup

## One-command mentor demo

For Windows, open this folder in VS Code and run either:

```powershell
.\run_ridehub.ps1
```

or double-click `RUN_RIDEHUB.bat`. The launcher creates the virtual environment,
installs dependencies when needed, shows a secure MySQL password popup, prepares
the MySQL 8.4 database, runs Django migrations, starts the server, and opens
Chrome at `http://127.0.0.1:8000/`. The root password is used only to create the
project database/user and is never saved. The full launcher also installs the
MySQL reporting view and booking-expiry procedure after migrations.

Inside VS Code, `Ctrl+Shift+B` runs the configured **Run RideHub in Chrome**
mentor-demo task without a database prompt.
For a fast UI-only mentor preview, use `RUN_RIDEHUB_DEMO.bat`; it opens the site
without requiring database credentials.

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set the local MySQL credentials.
4. Create the `vehicle_rental` database in MySQL 8.4.
5. Optional: add a restricted `GOOGLE_MAPS_API_KEY` to `.env` to enable Google
   Places autocomplete and reverse geocoding. Without it, manual addresses and
   browser geolocation still work.
6. Run the initial Django checks and migrations:

   ```bash
   python backend/manage.py check
   python backend/manage.py migrate
   ```

7. Start the development server:

   ```bash
   python backend/manage.py runserver
   ```

The proposal context is summarized in [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md).

Authentication integration details and free/paid provider notes are documented in
[`docs/AUTH_INTEGRATIONS.md`](docs/AUTH_INTEGRATIONS.md).

## Auth preview

Open `/auth/` through Django to preview the role-aware login and signup screens.
Use `?role=USER`, `?role=SHOPKEEPER`, or `?role=ADMIN` to open a role, and
`?mode=signup` for account creation. In `DEBUG=True`, the local OTP fallback
returns a development code in the UI; configure a real provider before deployment.
