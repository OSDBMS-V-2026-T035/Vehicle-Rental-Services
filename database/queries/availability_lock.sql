-- DBMS demonstration: serialize competing bookings for one vehicle.
-- The Django implementation is apps/bookings/services.py.
START TRANSACTION;
SELECT id, is_available, listing_status
FROM vehicles_vehicle
WHERE id = ?
FOR UPDATE;

-- Check an overlapping PENDING or CONFIRMED booking before INSERT.
SELECT id
FROM bookings_booking
WHERE vehicle_id = ?
  AND status IN ('PENDING', 'CONFIRMED')
  AND pickup_date <= ?
  AND return_date >= ?
FOR UPDATE;

-- If no row is returned, insert the booking and commit.
COMMIT;
