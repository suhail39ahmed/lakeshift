CREATE OR REPLACE PROCEDURE load_dim_customer AS
BEGIN
  MERGE INTO dim_customer d
  USING stg_customers s ON (d.customer_id = s.customer_id)
  WHEN MATCHED THEN UPDATE SET d.full_name = s.full_name, d.tier = s.tier, d.updated_at = SYSDATE
  WHEN NOT MATCHED THEN INSERT (customer_id, full_name, email, country, tier, updated_at)
    VALUES (s.customer_id, s.full_name, s.email, s.country, s.tier, SYSDATE);
END;