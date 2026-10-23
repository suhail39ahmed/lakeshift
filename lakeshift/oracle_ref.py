import csv, os, pathlib
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
 """CREATE TABLE fct_sales (order_month DATE, country VARCHAR2(10), tier VARCHAR2(10),
    orders NUMBER, revenue NUMBER, avg_order NUMBER, rank_in_country NUMBER)""",
]

def connect():
    return oracledb.connect(user="system", password=os.environ["ORACLE_PASSWORD"],
                            dsn="localhost:1521/FREEPDB1")

def reset(cur):
    for t in ["raw_customers", "raw_orders", "stg_customers", "dim_customer", "fct_sales"]:
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

def run_legacy(cur, plan):
    for name in plan["run_order"]:
        obj = next(o for o in plan["objects"] if o["name"] == name)
        cur.execute(pathlib.Path("legacy", obj["file"]).read_text())  # create the proc as-is
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
        for t in ["stg_customers", "dim_customer", "fct_sales"]:
            cols, rows = fetch(cur, t)
            print(t, len(rows), "rows")