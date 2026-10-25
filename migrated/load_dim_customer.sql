SELECT s.customer_id,
       NULLIF(TRIM(s.full_name), '') AS full_name,
       CASE WHEN d.customer_id IS NOT NULL THEN NULLIF(TRIM(d.email), '') ELSE NULLIF(TRIM(s.email), '') END AS email,
       CASE WHEN d.customer_id IS NOT NULL THEN NULLIF(TRIM(d.country), '') ELSE NULLIF(TRIM(s.country), '') END AS country,
       s.tier,
       CURRENT_DATE() AS updated_at
FROM stg_customers s
LEFT JOIN dim_customer d ON d.customer_id = s.customer_id;