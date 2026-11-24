import os
 
import MySQLdb


connection = MySQLdb.connect(
    host=os.getenv("MYSQL_HOST", "db"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    user=os.getenv("MYSQL_USER", "vehicle_rental_user"),
    passwd=os.getenv("MYSQL_PASSWORD", ""),
    db=os.getenv("MYSQL_DATABASE", "vehicle_rental"),
    charset="utf8mb4",
)

try:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE OR REPLACE VIEW verified_shop_inventory AS
            SELECT sp.id AS shop_id, sp.shop_name, sp.shop_address,
                   sp.latitude, sp.longitude, COUNT(v.id) AS approved_vehicle_count,
                   COALESCE(SUM(v.daily_rate), 0) AS inventory_daily_rate_total
            FROM accounts_shopkeeperprofile sp
            LEFT JOIN vehicles_vehicle v
              ON v.shopkeeper_id = sp.id
             AND v.listing_status = 'APPROVED'
             AND v.is_available = 1
            WHERE sp.verification_status = 'VERIFIED'
            GROUP BY sp.id, sp.shop_name, sp.shop_address, sp.latitude, sp.longitude
            """
        )
        cursor.execute("DROP PROCEDURE IF EXISTS sp_expire_pending_bookings")
        cursor.execute(
            """
            CREATE PROCEDURE sp_expire_pending_bookings(IN p_cutoff DATETIME)
            BEGIN
                DECLARE expired_count INT DEFAULT 0;

                UPDATE bookings_booking
                   SET status = 'CANCELLED', updated_at = UTC_TIMESTAMP()
                 WHERE status = 'PENDING' AND created_at < p_cutoff;
                SET expired_count = ROW_COUNT();

                UPDATE payments_paymenttransaction AS payment
                INNER JOIN bookings_booking AS booking ON booking.id = payment.booking_id
                   SET payment.status = 'CANCELLED', payment.updated_at = UTC_TIMESTAMP()
                 WHERE booking.status = 'CANCELLED'
                   AND booking.created_at < p_cutoff
                   AND payment.status = 'PENDING';

                SELECT expired_count AS expired_count;
            END
            """
        )
    connection.commit()
finally:
    connection.close()

print("MySQL reporting view and stored procedure installed.")
