-- Execute this file with the MySQL client, where DELIMITER is supported.
DELIMITER //
DROP PROCEDURE IF EXISTS sp_expire_pending_bookings//
CREATE PROCEDURE sp_expire_pending_bookings(IN p_cutoff DATETIME)
BEGIN
    UPDATE bookings_booking
       SET status = 'CANCELLED', updated_at = UTC_TIMESTAMP()
     WHERE status = 'PENDING'
       AND created_at < p_cutoff;
    SELECT ROW_COUNT() AS expired_count;
END//
DELIMITER ;
