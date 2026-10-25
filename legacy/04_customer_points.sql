CREATE OR REPLACE PACKAGE pkg_loyalty AS
  c_cap CONSTANT NUMBER := 1000;
  FUNCTION points_for(p_amount NUMBER, p_tier VARCHAR2) RETURN NUMBER;
END pkg_loyalty;
/
CREATE OR REPLACE PACKAGE BODY pkg_loyalty AS
  FUNCTION points_for(p_amount NUMBER, p_tier VARCHAR2) RETURN NUMBER IS
    v_mult NUMBER;
  BEGIN
    v_mult := CASE p_tier WHEN 'GOLD' THEN 2 WHEN 'SILVER' THEN 1.5 ELSE 1 END;
    RETURN FLOOR(NVL(p_amount, 0) * v_mult);
  END points_for;
END pkg_loyalty;
/
CREATE OR REPLACE PROCEDURE load_customer_points AS
  v_customer   NUMBER := NULL;
  v_balance    NUMBER := 0;
  v_prev_date  DATE := NULL;
  v_points     NUMBER;
  v_per_day    NUMBER;
BEGIN
  FOR r IN (SELECT o.customer_id, o.order_id, o.order_date, o.amount, o.status, d.tier
              FROM raw_orders o
              JOIN dim_customer d ON d.customer_id = o.customer_id
             WHERE o.status <> 'CANCELLED'
             ORDER BY o.customer_id, o.order_date, o.order_id) LOOP
    IF v_customer IS NULL OR r.customer_id <> v_customer THEN
      v_customer  := r.customer_id;      -- new customer: reset the running state
      v_balance   := 0;
      v_prev_date := NULL;
    END IF;

    v_points := pkg_loyalty.points_for(r.amount, r.tier);
    IF r.status = 'REFUNDED' THEN
      v_points := -v_points;              -- a refund takes its points back
    END IF;
    -- balance never drops below 0 and never exceeds the cap, checked on every order
    v_balance := GREATEST(LEAST(v_balance + v_points, pkg_loyalty.c_cap), 0);

    BEGIN
      v_per_day := ROUND(v_points / (r.order_date - v_prev_date), 2);
    EXCEPTION
      WHEN ZERO_DIVIDE THEN
        v_per_day := 0;                   -- two orders on the same day
    END;

    INSERT INTO customer_points (customer_id, order_id, order_date, points, balance, points_per_day)
    VALUES (r.customer_id, r.order_id, r.order_date, v_points, v_balance, v_per_day);

    v_prev_date := r.order_date;
  END LOOP;
END;
/
