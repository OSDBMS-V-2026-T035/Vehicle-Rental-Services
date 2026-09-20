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

The current frontend landing page is in `frontend/html/index.html`, with its styles,
interactions, and downloaded vehicle imagery in `frontend/css/`, `frontend/js/`, and
`frontend/images/`. Django serves the page through the root URL; the domain apps are
otherwise intentionally placeholders at this stage:
`accounts`, `shops`, `vehicles`, `bookings`, `payments`, `verification`,
`adminpanel`, and `notifications`.

## Initial setup

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set the local MySQL credentials.
4. Create the `vehicle_rental` database in MySQL 8.4.
5. Run the initial Django checks and migrations:

   ```bash
   python backend/manage.py check
   python backend/manage.py migrate
   ```

6. Start the development server:

   ```bash
   python backend/manage.py runserver
   ```

Business logic, data models, API endpoints, and user-facing pages will be added in later iterations.

The proposal context and the OS/DBMS integration mapping are summarized in
[`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md).

Authentication integration details and free/paid provider notes are documented in
[`docs/AUTH_INTEGRATIONS.md`](docs/AUTH_INTEGRATIONS.md).

## Auth preview

Open `/auth/` through Django to preview the role-aware login and signup screens.
Use `?role=USER`, `?role=SHOPKEEPER`, or `?role=ADMIN` to open a role, and
`?mode=signup` for account creation. In `DEBUG=True`, the local OTP fallback
returns a development code in the UI; configure a real provider before deployment.
