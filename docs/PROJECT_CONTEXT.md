# Project context

This project is based on the Vehicle Rental Services proposal for team
`OSDBMS-V-2026-T035`. The project documents identify three primary stakeholders:

- Customers who discover, compare, book, pay for, and review vehicles.
- Local sellers who manage shops, verification details, vehicles, pricing, and availability.
- Administrators who manage users, sellers, vehicles, bookings, payments, verification, reports, and audit records.

## Domain areas and current milestone

The Django app layout reflects the proposal's major responsibilities:

| Domain | Planned responsibility |
| --- | --- |
| `accounts` | Authentication, profiles, email OTP, and role-based access |
| `shops` | Shopkeeper onboarding, verification status, global location, and nearby search |
| `vehicles` | Vehicle listings, categories, pricing, photos, availability, and admin moderation |
| `bookings` | Reservations, history, seven-day date rules, and concurrency-safe booking |
| `payments` | Payment records and future payment-service integration |
| `verification` | Seller, vehicle, and customer verification workflows |
| `adminpanel` | Administration, reports, approvals, and audit views |
| `notifications` | Booking, payment, verification, and background-job notifications |

## OS and DBMS integration implemented

The MySQL layer now has normalized relational models, keys, constraints, indexes,
joins, a reporting view, a stored procedure, transactions, audit records, and
concurrency control. The booking workflow is the primary DBMS/OS integration point:
transactions and row locking prevent double-booking when multiple customers request
the same vehicle concurrently.

OS-focused implementation now includes a threaded local preview server, filesystem
vehicle-media management, role/access control, scheduled booking expiry, a MySQL
wait-for graph deadlock checker, safe retry-oriented recovery guidance, and a MySQL
backup launcher. Linux service/cron deployment can use the same management commands.

## Stack decision

One proposal page contains an earlier React/Node/Express approach. The direct project
implementation request specifies HTML, CSS, JavaScript, Python, Django, and MySQL 8.4,
so this repository follows that requested stack and does not add React, Node, Express,
or another frontend framework.
