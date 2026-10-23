SELECT
    s.customer_id,
    s.full_name,
    s.email,
    s.country,
    s.tier,
    CURRENT_TIMESTAMP() AS updated_at
FROM stg_customers s;