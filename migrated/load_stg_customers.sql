WITH src AS (
  SELECT
    c.customer_id,
    INITCAP(TRIM(c.first_name)) || ' ' || INITCAP(TRIM(c.last_name)) AS full_name,
    LOWER(COALESCE(NULLIF(c.email, ''), 'unknown@none')) AS email,
    COALESCE(NULLIF(c.country, ''), 'XX') AS country,
    DATE_TRUNC('month', c.signup_date) AS signup_month,
    CASE
      WHEN c.tier_code = 'G' THEN 'GOLD'
      WHEN c.tier_code = 'S' THEN 'SILVER'
      ELSE 'BRONZE'
    END AS tier
  FROM raw_customers c
  WHERE c.is_deleted = 'N'
)
SELECT
  COALESCE(src.customer_id, t.customer_id) AS customer_id,
  CASE WHEN src.customer_id IS NOT NULL THEN src.full_name ELSE t.full_name END AS full_name,
  CASE WHEN src.customer_id IS NOT NULL THEN src.email ELSE t.email END AS email,
  CASE WHEN src.customer_id IS NOT NULL THEN src.country ELSE t.country END AS country,
  CASE WHEN src.customer_id IS NOT NULL THEN src.signup_month ELSE t.signup_month END AS signup_month,
  CASE WHEN src.customer_id IS NOT NULL THEN src.tier ELSE t.tier END AS tier
FROM stg_customers t
FULL OUTER JOIN src ON t.customer_id = src.customer_id;