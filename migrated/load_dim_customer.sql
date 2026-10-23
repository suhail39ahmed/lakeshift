WITH src AS (
  SELECT s.customer_id,
         s.full_name,
         s.email,
         s.country,
         s.tier
  FROM stg_customers s
),
matched AS (
  SELECT d.customer_id,
         src.full_name,
         d.email,
         d.country,
         src.tier,
         CURRENT_DATE() AS updated_at
  FROM dim_customer d
  JOIN src ON d.customer_id = src.customer_id
),
unchanged AS (
  SELECT d.customer_id,
         d.full_name,
         d.email,
         d.country,
         d.tier,
         d.updated_at
  FROM dim_customer d
  LEFT JOIN src ON d.customer_id = src.customer_id
  WHERE src.customer_id IS NULL
),
inserted AS (
  SELECT src.customer_id,
         src.full_name,
         src.email,
         src.country,
         src.tier,
         CURRENT_DATE() AS updated_at
  FROM src
  LEFT JOIN dim_customer d ON d.customer_id = src.customer_id
  WHERE d.customer_id IS NULL
)
SELECT customer_id, full_name, email, country, tier, updated_at FROM matched
UNION ALL
SELECT customer_id, full_name, email, country, tier, updated_at FROM unchanged
UNION ALL
SELECT customer_id, full_name, email, country, tier, updated_at FROM inserted;