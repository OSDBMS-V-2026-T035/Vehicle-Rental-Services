-- MySQL 8.4 reference query for global nearby-shop search.
-- Django currently applies the same Haversine calculation in Python so it
-- remains portable without a GIS extension.
SELECT id, shop_name, shop_address,
       (6371 * 2 * ASIN(SQRT(
           POWER(SIN(RADIANS(latitude - :latitude) / 2), 2) +
           COS(RADIANS(:latitude)) * COS(RADIANS(latitude)) *
           POWER(SIN(RADIANS(longitude - :longitude) / 2), 2)
       ))) AS distance_km
FROM accounts_shopkeeperprofile
WHERE verification_status = 'VERIFIED'
  AND latitude IS NOT NULL
  AND longitude IS NOT NULL
HAVING distance_km <= :radius_km
ORDER BY distance_km;
