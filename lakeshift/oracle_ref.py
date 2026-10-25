import csv, os, pathlib, re
from datetime import date
import oracledb
from dotenv import load_dotenv

load_dotenv()

DDL = [
 """CREATE TABLE raw_customers (customer_id NUMBER, first_name VARCHAR2(50),
    last_name VARCHAR2(50), email VARCHAR2(100), country VARCHAR2(10),
    signup_date DATE, tier_code VARCHAR2(5), is_deleted VARCHAR2(1))""",
 """CREATE TABLE raw_orders (order_id NUMBER, customer_id NUMBER,
    order_date DATE, amount NUMBER, status VARCHAR2(20))""",
 """CREATE TABLE stg_customers (customer_id NUMBER, full_name VARCHAR2(200),
    email VARCHAR2(100), country VARCHAR2(10), signup_month DATE, tier VARCHAR2(10))""",
 """CREATE TABLE dim_customer (customer_id NUMBER, full_name VARCHAR2(200),
    email VARCHAR2(100), country VARCHAR2(10), tier VARCHAR2(10), updated_at DATE)""",
 """CREATE TABLE raw_referrals (customer_id NUMBER, referred_by NUMBER)""",
 """CREATE TABLE customer_points (customer_id NUMBER, order_id NUMBER, order_date DATE,
    points NUMBER, balance NUMBER, points_per_day NUMBER)""",
 """CREATE TABLE referral_tree (customer_id NUMBER, root_id NUMBER, depth NUMBER,
    path VARCHAR2(400), is_leaf NUMBER)""",
 """CREATE TABLE order_gaps (customer_id NUMBER, order_id NUMBER, order_date DATE,
    prev_order_date DATE, days_since_prev NUMBER, months_since_prev NUMBER,
    next_expected DATE, avg_gap_days NUMBER)""",
 """CREATE TABLE fct_sales (order_month DATE, country VARCHAR2(10), tier VARCHAR2(10),
    orders NUMBER, revenue NUMBER, avg_order NUMBER, rank_in_country NUMBER)""",
]

def settings():
    """Oracle connection settings. Defaults match the local docker-compose setup."""
    return {"host": os.environ.get("ORACLE_HOST", "127.0.0.1"),
            "port": int(os.environ.get("ORACLE_PORT", "1521")),
            "user": os.environ.get("ORACLE_USER", "system"),
            "service": os.environ.get("ORACLE_SERVICE", "FREEPDB1")}

def connect():
    c = settings()
    return oracledb.connect(user=c["user"], password=os.environ["ORACLE_PASSWORD"],
                            dsn=f"{c['host']}:{c['port']}/{c['service']}")

def reset(cur):
    for t in ["raw_customers", "raw_orders", "raw_referrals", "stg_customers", "dim_customer",
              "fct_sales", "customer_points", "referral_tree", "order_gaps"]:
        try:
            cur.execute(f"DROP TABLE {t} PURGE")
        except oracledb.DatabaseError:
            pass                              # table didn't exist yet
    for ddl in DDL:
        cur.execute(ddl)

def load(cur):
    rows = list(csv.DictReader(open("data/raw_customers.csv")))
    cur.executemany("INSERT INTO raw_customers VALUES (:1,:2,:3,:4,:5,:6,:7,:8)",
        [(int(r["customer_id"]), r["first_name"], r["last_name"], r["email"], r["country"],
          date.fromisoformat(r["signup_date"]), r["tier_code"], r["is_deleted"]) for r in rows])
    rows = list(csv.DictReader(open("data/raw_orders.csv")))
    cur.executemany("INSERT INTO raw_orders VALUES (:1,:2,:3,:4,:5)",
        [(int(r["order_id"]), int(r["customer_id"]), date.fromisoformat(r["order_date"]),
          float(r["amount"]) if r["amount"] else None, r["status"]) for r in rows])
    rows = list(csv.DictReader(open("data/raw_referrals.csv")))
    cur.executemany("INSERT INTO raw_referrals VALUES (:1,:2)",
        [(int(r["customer_id"]), int(r["referred_by"]) if r["referred_by"] else None) for r in rows])

def statements(text):
    """A legacy file may hold several CREATE statements separated by a line with only '/'."""
    parts = re.split(r"(?m)^\s*/\s*$", text)
    return [p.strip() for p in parts if p.strip()]

def run_legacy(cur, plan):
    for name in plan["run_order"]:
        obj = next(o for o in plan["objects"] if o["name"] == name)
        for stmt in statements(pathlib.Path("legacy", obj["file"]).read_text()):
            cur.execute(stmt)                                         # create package/proc as-is
        cur.execute("SELECT name || ': ' || text FROM user_errors WHERE ROWNUM = 1")
        if (err := cur.fetchone()):
            raise RuntimeError(f"{obj['file']}: did not compile: {err[0]}")
        cur.callproc(name)                                            # run it
        print(f"oracle ran {name}")

def fetch(cur, table):
    cur.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    return cols, cur.fetchall()

if __name__ == "__main__":
    import json
    plan = json.loads(pathlib.Path("migrated/plan.json").read_text())
    with connect() as conn:
        cur = conn.cursor()
        reset(cur); load(cur); run_legacy(cur, plan); conn.commit()
        for t in ["stg_customers", "dim_customer", "fct_sales", "customer_points", "referral_tree", "order_gaps"]:
            cols, rows = fetch(cur, t)
            print(t, len(rows), "rows")