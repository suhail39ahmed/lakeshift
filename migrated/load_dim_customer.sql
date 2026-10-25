SELECT
    COALESCE(s.customer_id, d.customer_id) AS customer_id,
    COALESCE(s.full_name, d.full_name) AS full_name,
    COALESCE(s.email, d.email) AS email,
    COALESCE(s.country, d.country) AS country,
    COALESCE(s.tier, d.tier) AS tier,
    CASE WHEN s.customer_id IS NOT NULL THEN CURRENT_DATE() ELSE d.updated_at END AS updated_at
FROM dim_customer d
FULL OUTER JOIN stg_customers s
  ON d.customer_id = s.customer_id