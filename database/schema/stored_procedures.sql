-- Execute this file with the MySQL client, where DELIMITER is supported.
DELIMITER //
DROP PROCEDURE IF EXISTS sp_expire_pending_bookings//
CREATE PROCEDURE sp_expire_pending_bookings(IN p_cutoff DATETIME)
BEGIN
    DECLARE expired_count INT DEFAULT 0;

    UPDATE bookings_booking
       SET status = 'CANCELLED', updated_at = UTC_TIMESTAMP()
     WHERE status = 'PENDING'
       AND created_at < p_cutoff;
    SET expired_count = ROW_COUNT();

    UPDATE payments_paymenttransaction AS payment
    INNER JOIN bookings_booking AS booking ON booking.id = payment.booking_id
       SET payment.status = 'CANCELLED', payment.updated_at = UTC_TIMESTAMP()
     WHERE booking.status = 'CANCELLED'
       AND booking.created_at < p_cutoff
       AND payment.status = 'PENDING';

    SELECT expired_count AS expired_count;
END//
DELIMITER ;
