# MySQL 8.4 schema extensions

Run the Django migrations first. Then, using a MySQL 8.4 client with the project database selected, install:

```text
SOURCE database/schema/reporting_views.sql;
SOURCE database/schema/stored_procedures.sql;
```

The reporting view is read-only and supports inventory summaries for verified shops. The stored procedure expires stale pending bookings and is callable by a scheduled maintenance task. Django management commands provide the same expiry behavior in application code, so the project remains testable without relying only on MySQL-specific routines.
