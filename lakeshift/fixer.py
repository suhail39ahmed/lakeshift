import json, pathlib, re
from lakeshift.llm import chat, NANO, SUPER, ULTRA, usage
from lakeshift.verifier import verify
from lakeshift.researcher import research
from lakeshift.privacy import mask_report, stats as privacy

LADDER = [NANO, SUPER, ULTRA]    # cheapest first; escalate only when proof fails

SYSTEM = """You repair a Snowflake SQL translation of an Oracle PL/SQL procedure.
The harness runs:  INSERT OVERWRITE INTO <target> <your SELECT>
so you must return ONE SELECT (or WITH ... SELECT) whose rows are the COMPLETE
final contents of the target table after the legacy procedure runs.
The target table already holds its previous rows and can be read in your SELECT.
To emulate MERGE: matched rows take updated columns from the source, unmatched
target rows are kept unchanged, unmatched source rows are inserted.
Oracle CONNECT BY, and cursor loops that carry a running value from row to row,
become WITH RECURSIVE in Snowflake. Oracle date - date is a number of days.
A plain INSERT procedure starts from an EMPTY target: just return the rows it inserts.
In a recursive CTE, cast anchor columns to the recursive column type (e.g. CAST(x AS VARCHAR) for paths).
Snowflake supports MONTHS_BETWEEN, LAG, NVL; TRUNC(d + NUMTODSINTERVAL(n,'DAY')) with a fractional n becomes DATEADD(day, FLOOR(n), d).
Return exactly the target table's columns, in order.
Keep your reasoning short. Always end with your best complete SQL, even if unsure.
Never write MERGE, INSERT, UPDATE or DELETE. No explanations, no markdown."""

def clean(sql):
    """Return only the SQL statement from a model reply, or "" if there is none."""
    sql = (sql or "").strip()
    sql = re.sub(r"(?is)<think>.*?</think>", "", sql)          # drop the model's thinking notes
    sql = re.sub(r"(?is)^.*</think>", "", sql).strip()          # (opening tag sometimes missing)
    fences = re.findall(r"```(?:sql)?\s*(.*?)```", sql, flags=re.S | re.I)
    if fences:                                  # the LAST code block is the final answer
        sql = fences[-1]
    m = re.search(r"(?ims)^[ \t]*(WITH|SELECT)\s.*", sql)
    if not m:
        return ""
    sql = m.group(0)
    sql = re.split(r";\s*(?:\n|$)", sql)[0]     # one statement: stop at the first ;
    sql = re.split(r"\n\s*\n(?=[A-Z][a-z]+ [a-z])", sql)[0]   # drop a trailing prose paragraph
    if re.search(r"\*\*|^#+ |^\s*[-*] ", sql, flags=re.M):    # markdown left = not SQL
        return ""
    return sql.strip()
def safe_verify(plan, sqls):
    """Verify; if Snowflake's login expired mid-run (laptop slept), reconnect and retry once."""
    report = verify(plan, sqls)
    if any("390112" in r.get("reason", "") for r in report.values()):
        print("    snowflake session expired - reconnecting and re-verifying")
        report = verify(plan, sqls)
    return report

def run():
    plan = json.loads(pathlib.Path("migrated/plan.json").read_text(encoding="utf-8"))
    sqls = {o["name"]: pathlib.Path("migrated", o["name"] + ".sql").read_text(encoding="utf-8")
            for o in plan["objects"]}
    report, log = safe_verify(plan, sqls), []
    evidence = {}

    for model in LADDER:
        failing = [n for n, r in report.items() if r["status"] != "PASS"]
        if not failing:
            break
        for n in failing:
            obj = next(o for o in plan["objects"] if o["name"] == n)
            legacy = pathlib.Path("legacy", obj["file"]).read_text(encoding="utf-8")
            if n not in evidence:                       # research once per object
                query = (f"Oracle to Snowflake: {'; '.join(obj['risks'])}. "
                         f"{report[n].get('scenario', '')}")[:400]
                evidence[n] = research(query)
                print(f"    researched {n}: {len(evidence[n][1])} doc sources")
            prompt = (f"Oracle source:\n{legacy}\n\nCurrent Snowflake SQL:\n{sqls[n]}\n\n"
                      f"Official documentation evidence:\n{evidence[n][0]}\n\n"
                      f"Verifier report:\n{json.dumps(mask_report(report[n]), ensure_ascii=False)[:4000]}")
            reply = chat(model, SYSTEM, prompt)
            log_dir = pathlib.Path("migrated", "replies"); log_dir.mkdir(exist_ok=True)
            (log_dir / f"{n}.{model.split('/')[-1]}.txt").write_text(reply or "", encoding="utf-8")
            fixed = clean(reply)
            if fixed and fixed.strip() == sqls[n].strip():
                print(f"    {model.split('/')[-1]} returned the same SQL for {n} unchanged")
            if fixed:                       # keep last real SQL if the model rambled
                sqls[n] = fixed
            else:
                raw = pathlib.Path("migrated", "rejected"); raw.mkdir(exist_ok=True)
                (raw / f"{n}.{model.split('/')[-1]}.txt").write_text(reply or "", encoding="utf-8")
                start = " ".join((reply or "<empty reply>").split())[:120]
                print(f"    {model.split('/')[-1]} reply for {n} rejected (no SQL found): {start}")
        report = safe_verify(plan, sqls)
        for n in failing:
            log.append({"object": n, "model": model, "result": report[n]["status"],
                        "sources": evidence.get(n, ("", []))[1]})
            print(f"{model.split('/')[-1]:40} {n:22} -> {report[n]['status']}")

    for n, sql in sqls.items():
        pathlib.Path("migrated", n + ".sql").write_text(sql, encoding="utf-8")
    pathlib.Path("migrated/report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    pathlib.Path("migrated/fix_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print("\nfinal:", {n: r["status"] for n, r in report.items()})
    print("tokens:", usage)
    print(f"privacy: {privacy['masked']} text values masked, 0 raw customer values sent to the model")

if __name__ == "__main__":
    run()


