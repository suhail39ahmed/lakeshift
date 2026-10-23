import json, pathlib
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from lakeshift import oracle_ref, warehouse

SF_DDL = {
 "stg_customers": "CUSTOMER_ID NUMBER, FULL_NAME VARCHAR, EMAIL VARCHAR, COUNTRY VARCHAR, SIGNUP_MONTH DATE, TIER VARCHAR",
 "dim_customer":  "CUSTOMER_ID NUMBER, FULL_NAME VARCHAR, EMAIL VARCHAR, COUNTRY VARCHAR, TIER VARCHAR, UPDATED_AT DATE",
 "fct_sales":     "ORDER_MONTH DATE, COUNTRY VARCHAR, TIER VARCHAR, ORDERS NUMBER, REVENUE NUMBER(18,2), AVG_ORDER NUMBER(18,2), RANK_IN_COUNTRY NUMBER",
}
IGNORE = {"UPDATED_AT"}          # load timestamps never match across systems

def fmt(v):
    if v is None: return "∅"
    if isinstance(v, datetime): return v.date().isoformat()
    if isinstance(v, date): return v.isoformat()
    if isinstance(v, (int, float, Decimal)): return f"{float(v):.2f}"
    return str(v)

def normalize(cols, rows):
    keep = [i for i, c in enumerate(cols) if c.upper() not in IGNORE]
    names = [cols[i].upper() for i in keep]
    return names, Counter(tuple(fmt(r[i]) for i in keep) for r in rows)

def compare(ref, cand):
    (rc, rrows), (cc, crows) = ref, cand
    if rc != cc:
        return {"status": "FAIL", "reason": f"columns differ: oracle={rc} snowflake={cc}"}
    only_ref, only_cand = rrows - crows, crows - rrows
    if not only_ref and not only_cand:
        return {"status": "PASS", "rows": sum(rrows.values())}
    return {"status": "FAIL", "columns": rc,
            "rows_oracle": sum(rrows.values()), "rows_snowflake": sum(crows.values()),
            "mismatched": sum(only_ref.values()) + sum(only_cand.values()),
            "sample_oracle_only": [list(r) for r in list(only_ref)[:5]],
            "sample_snowflake_only": [list(r) for r in list(only_cand)[:5]]}

def sf_fetch(cur, table):
    cur.execute(f"SELECT * FROM {table}")
    return [d[0] for d in cur.description], cur.fetchall()

def seed(scur, table, truth_table):
    cols, rows = truth_table
    scur.execute(f"TRUNCATE TABLE {table}")
    if rows:
        ph = ",".join(["%s"] * len(cols))
        scur.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph})", rows)

def verify(plan, sql_by_name):
    # 1. truth: run untouched legacy code in Oracle
    with oracle_ref.connect() as oconn:
        ocur = oconn.cursor()
        oracle_ref.reset(ocur); oracle_ref.load(ocur)
        oracle_ref.run_legacy(ocur, plan); oconn.commit()
        truth = {t: oracle_ref.fetch(ocur, t) for t in SF_DDL}

    # 2. candidate: run translated SQL in Snowflake, in planner order
    report = {}
    sconn = warehouse.connect()
    try:
        scur = sconn.cursor()
        for t, cols in SF_DDL.items():
            scur.execute(f"CREATE OR REPLACE TABLE {t} ({cols})")
        for name in plan["run_order"]:
            obj = next(o for o in plan["objects"] if o["name"] == name)
            target = obj["writes"][0].lower()
            for src in obj["reads"]:
                if src.lower() in truth:      # upstream we produced: use Oracle's truth
                    seed(scur, src.lower(), truth[src.lower()])
            sql = sql_by_name[name].strip().rstrip(";")
            try:
                scur.execute(f"INSERT OVERWRITE INTO {target} {sql}")
                cand = sf_fetch(scur, target)
                report[name] = compare(normalize(*truth[target]), normalize(*cand))
            except Exception as e:
                report[name] = {"status": "ERROR", "reason": str(e)[:500]}
    finally:
        sconn.close()
    return report

if __name__ == "__main__":
    plan = json.loads(pathlib.Path("migrated/plan.json").read_text())
    sqls = {o["name"]: pathlib.Path("migrated", o["name"] + ".sql").read_text()
            for o in plan["objects"]}
    report = verify(plan, sqls)
    pathlib.Path("migrated/report.json").write_text(json.dumps(report, indent=2))
    for name, r in report.items():
        print(f"{r['status']:5}  {name}  {r.get('mismatched', '')}")
    print(json.dumps(report, indent=2, ensure_ascii=False))