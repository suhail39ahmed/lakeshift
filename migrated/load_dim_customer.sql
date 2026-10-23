SELECT
    s.customer_id,
    COALESCE(d.full_name, s.full_name) AS full_name,
    COALESCE(d.email, s.email) AS email,
    COALESCE(d.country, s.country) AS country,
    COALESCE(d.tier, s.tier) AS tier,
    CURRENT_DATE() AS updated_at
FROM stg_customers s
LEFT JOIN dim_customer d ON d.customer_id = s.customer_id;