WITH matched AS (
  SELECT s.customer_id,
         s.full_name,
         s.email,
         s.country,
         s.tier,
         CURRENT_TIMESTAMP() AS updated_at
  FROM stg_customers s
  JOIN dim_customer d ON d.customer_id = s.customer_id
),
unchanged AS (
  SELECT d.customer_id,
         d.full_name,
         d.email,
         d.country,
         d.tier,
         d.updated_at
  FROM dim_customer d
  WHERE NOT EXISTS (SELECT 1 FROM stg_customers s WHERE s.customer_id = d.customer_id)
),
inserted AS (
  SELECT s.customer_id,
         s.full_name,
         s.email,
         s.country,
         s.tier,
         CURRENT_TIMESTAMP() AS updated_at
  FROM stg_customers s
  WHERE NOT EXISTS (SELECT 1 FROM dim_customer d WHERE d.customer_id = s.customer_id)
)
SELECT customer_id, full_name, email, country, tier, updated_at
FROM matched
UNION ALL
SELECT customer_id, full_name, email, country, tier, updated_at
FROM unchanged
UNION ALL
SELECT customer_id, full_name, email, country, tier, updated_at
FROM inserted;