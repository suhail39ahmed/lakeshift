WITH merged AS (
  SELECT
    d.customer_id,
    COALESCE(s.full_name, d.full_name) AS full_name,
    COALESCE(s.email, d.email) AS email,
    COALESCE(s.country, d.country) AS country,
    COALESCE(s.tier, d.tier) AS tier,
    CASE WHEN s.customer_id IS NOT NULL THEN CURRENT_DATE() ELSE d.updated_at END AS updated_at
  FROM dim_customer d
  LEFT JOIN stg_customers s ON d.customer_id = s.customer_id
)
SELECT
  customer_id,
  full_name,
  email,
  country,
  tier,
  updated_at
FROM merged
UNION ALL
SELECT
  s.customer_id,
  s.full_name,
  s.email,
  s.country,
  s.tier,
  CURRENT_DATE() AS updated_at
FROM stg_customers s
LEFT JOIN dim_customer d ON d.customer_id = s.customer_id
WHERE d.customer_id IS NULL