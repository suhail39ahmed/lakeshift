SELECT
    c.customer_id,
    INITCAP(TRIM(c.first_name)) || ' ' || INITCAP(TRIM(c.last_name)) AS full_name,
    LOWER(COALESCE(NULLIF(c.email, ''), 'unknown@none')) AS email,
    COALESCE(NULLIF(c.country, ''), 'XX') AS country,
    DATE_TRUNC('month', c.signup_date) AS signup_month,
    CASE c.tier_code
        WHEN 'G' THEN 'GOLD'
        WHEN 'S' THEN 'SILVER'
        ELSE 'BRONZE'
    END AS tier
FROM raw_customers c
WHERE c.is_deleted = 'N';