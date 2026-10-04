-- MySQL 8.4 reporting view used for inventory/reporting demonstrations.
CREATE OR REPLACE VIEW verified_shop_inventory AS
SELECT
    sp.id AS shop_id,
    sp.shop_name,
    sp.shop_address,
    sp.latitude,
    sp.longitude,
    COUNT(v.id) AS approved_vehicle_count,
    COALESCE(SUM(v.daily_rate), 0) AS inventory_daily_rate_total
FROM accounts_shopkeeperprofile sp
LEFT JOIN vehicles_vehicle v
    ON v.shopkeeper_id = sp.id
   AND v.listing_status = 'APPROVED'
   AND v.is_available = 1
WHERE sp.verification_status = 'VERIFIED'
GROUP BY sp.id, sp.shop_name, sp.shop_address, sp.latitude, sp.longitude;
