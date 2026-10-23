SELECT
    c.customer_id,
    INITCAP(TRIM(c.first_name)) || ' ' || INITCAP(TRIM(c.last_name)) AS full_name,
    LOWER(COALESCE(NULLIF(c.email, ''), 'unknown@none')) AS email,
    COALESCE(NULLIF(c.country, ''), 'XX') AS country,
    TRUNC(c.signup_date, 'MONTH') AS signup_month,
    CASE
        WHEN c.tier_code = 'G' THEN 'GOLD'
        WHEN c.tier_code = 'S' THEN 'SILVER'
        WHEN c.tier_code = 'BRONZE' THEN 'BRONZE'
    END AS tier
FROM raw_customers c
WHERE c.is_deleted = 'N';