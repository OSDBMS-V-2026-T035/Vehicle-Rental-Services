# Project context

This project is based on the Vehicle Rental Services proposal for team
`OSDBMS-V-2026-T035`. The project documents identify three primary stakeholders:

- Customers who discover, compare, book, pay for, and review vehicles.
- Local sellers who manage shops, verification details, vehicles, pricing, and availability.
- Administrators who manage users, sellers, vehicles, bookings, payments, verification, reports, and audit records.

## Planned domain areas

The Django app layout reflects the proposal's major responsibilities:

| Domain | Planned responsibility |
| --- | --- |
| `accounts` | Authentication, profiles, and role-based access |
| `shops` | Local seller and shop registration/details |
| `vehicles` | Vehicle listings, categories, pricing, and availability |
| `bookings` | Reservations, cancellations, history, and concurrency-safe booking |
| `payments` | Payment records and future payment-service integration |
| `verification` | Seller, vehicle, and customer verification workflows |
| `adminpanel` | Administration, reports, approvals, and audit views |
| `notifications` | Booking, payment, verification, and background-job notifications |

## OS and DBMS integration direction

The planned MySQL layer will support normalized relational data, keys, constraints,
indexes, joins, views, transactions, and concurrency control. The booking workflow
is the primary DBMS/OS integration point: transactions and row locking should prevent
double-booking when multiple customers request the same vehicle concurrently.

Future OS-focused work can demonstrate critical sections, synchronization, race
condition handling, deadlock detection/recovery, scheduling of background jobs,
file management, permissions, and audit-friendly operations. Those concerns are
intentionally represented by the app boundaries and database folders now, without
implementing business logic in this initial website pass.

## Stack decision

One proposal page contains an earlier React/Node/Express approach. The direct project
implementation request specifies HTML, CSS, JavaScript, Python, Django, and MySQL 8.4,
so this repository follows that requested stack and does not add React, Node, Express,
or another frontend framework.

