CREATE OR REPLACE PROCEDURE load_stg_customers AS
BEGIN
  INSERT INTO stg_customers (customer_id, full_name, email, country, signup_month, tier)
  SELECT c.customer_id,
         INITCAP(TRIM(c.first_name)) || ' ' || INITCAP(TRIM(c.last_name)),
         LOWER(NVL(c.email, 'unknown@none')),
         NVL(c.country, 'XX'),
         TRUNC(c.signup_date, 'MM'),
         DECODE(c.tier_code, 'G', 'GOLD', 'S', 'SILVER', 'BRONZE')
  FROM raw_customers c
  WHERE c.is_deleted = 'N';
END;