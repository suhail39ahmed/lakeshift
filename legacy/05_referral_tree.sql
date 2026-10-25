CREATE OR REPLACE PROCEDURE load_referral_tree AS
BEGIN
  INSERT INTO referral_tree (customer_id, root_id, depth, path, is_leaf)
  SELECT r.customer_id,
         CONNECT_BY_ROOT r.customer_id,
         LEVEL,
         SYS_CONNECT_BY_PATH(r.customer_id, '/'),
         CONNECT_BY_ISLEAF
  FROM raw_referrals r
  START WITH r.referred_by IS NULL
  CONNECT BY PRIOR r.customer_id = r.referred_by;
END;
