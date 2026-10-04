# OS and DBMS implementation map

This project follows the PBL proposal while keeping the requested HTML/CSS/JavaScript + Django + MySQL stack.

## DBMS concepts present in the application

- **Normalized relational data:** users, shopkeeper profiles, vehicles, bookings, and audit logs are separate Django models with foreign-key relationships.
- **Constraints:** unique email, unique phone number, unique vehicle registration number, validated dates, price/year/seat ranges, and the booking return-date check constraint.
- **Indexes:** role/status indexes, vehicle search indexes, booking availability indexes, and audit lookup indexes are declared in model metadata and migrations.
- **Transactions:** signup, admin moderation, audit-log creation, and booking creation use `transaction.atomic()`.
- **Concurrency control:** `apps/bookings/services.py` uses `select_for_update()` before checking overlapping bookings, preventing two concurrent requests from reserving the same vehicle.
- **Views and query filtering:** approved shops/vehicles are the only public search results; pending or rejected marketplace data stays private.
- **Auditability:** every admin approve/reject/revoke/restore operation creates an `AuditLog` row.
- **Database view:** `database/schema/reporting_views.sql` provides verified-shop inventory totals for reporting screens.
- **Stored procedure:** `database/schema/stored_procedures.sql` provides a MySQL 8.4 booking-expiry routine.

## OS concepts present or prepared

- **Process/service separation:** Django runs as the application process; the database and uploaded media are separate resources.
- **File management:** vehicle images are stored under `media/vehicle-images/` while their metadata remains in MySQL.
- **Access control:** Django sessions, role checks, account activation, upload validation, and separate admin/shopkeeper routes enforce authorization.
- **Synchronization and critical sections:** database row locks protect the vehicle-booking critical section.
- **Scheduling/background work:** the architecture leaves notifications, booking expiry, backups, and reports as independent worker/scheduled tasks instead of putting long work in HTTP requests.
- **Linux deployment readiness:** `run_ridehub.ps1` is a local launcher; deployment can map the same settings to a Linux service, restricted media directory, and scheduled MySQL backup.
- **Scheduled maintenance:** `expire_bookings` cancels stale pending requests, while `run_booking_maintenance.ps1` runs expiry and deadlock inspection together.
- **Deadlock inspection:** `detect_deadlocks` reads MySQL 8.4 `performance_schema.data_lock_waits`, builds a wait-for graph, reports cycles, and leaves recovery to a safe retry policy rather than killing arbitrary transactions.

## Marketplace authenticity flow

1. A shopkeeper signs up with email OTP and receives a temporary login.
2. The account can edit its shop profile but cannot submit vehicles while `PENDING`.
3. An admin approves, rejects, or revokes the shopkeeper from `/control-panel/`.
4. Only `VERIFIED` shopkeepers can submit vehicle records and sample photos.
5. An admin approves or rejects each vehicle listing.
6. Public search returns only approved vehicles and verified active shops.

## What is now executable

- `python backend/manage.py expire_bookings --older-than-hours 24`
- `python backend/manage.py detect_deadlocks`
- `scripts/run_booking_maintenance.ps1` for the two maintenance jobs together
- MySQL reporting view and stored procedure files under `database/schema/`

## Location and dates

Google Places autocomplete is optional and no longer restricted to India. Browser geolocation remains the fallback. Search filters by global latitude/longitude and a radius; a directions link is generated for every listing with coordinates. Pickup dates cannot be in the past, and round-trip return dates cannot exceed seven days after pickup.
