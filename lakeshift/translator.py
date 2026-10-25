import json, pathlib, re
from concurrent.futures import ThreadPoolExecutor
from lakeshift.llm import chat, NANO, usage
from lakeshift.planner import plan

SYSTEM = """You translate Oracle PL/SQL ETL procedures to Snowflake SQL.
Return ONLY one SELECT statement (no INSERT/MERGE, no procedure wrapper)
whose result equals the rows the procedure writes to its target table.
Preserve Oracle semantics exactly, especially the listed risks.
Remember: in Oracle '' IS NULL; in Snowflake '' is NOT NULL.
Replace SYSDATE with CURRENT_DATE(). Use Snowflake syntax only.
No explanations, no markdown."""

def translate(obj, folder="legacy"):
    src = pathlib.Path(folder, obj["file"]).read_text(encoding="utf-8")
    prompt = f"Risks to handle: {obj['risks']}\n\nProcedure:\n{src}"
    sql = chat(NANO, SYSTEM, prompt)
    sql = re.sub(r"^```\w*|```$", "", sql.strip(), flags=re.M).strip()
    out = pathlib.Path("migrated", obj["name"] + ".sql")
    out.parent.mkdir(exist_ok=True)
    out.write_text(sql, encoding="utf-8")
    return obj["name"], sql

def translate_all(p, folder="legacy"):
    with ThreadPoolExecutor(max_workers=4) as pool:          # parallel agents
        results = dict(pool.map(lambda o: translate(o, folder), p["objects"]))
    pathlib.Path("migrated/plan.json").write_text(json.dumps(p, indent=2), encoding="utf-8")
    return results

if __name__ == "__main__":
    p = plan()
    with ThreadPoolExecutor(max_workers=4) as pool:          # parallel agents
        for name, sql in pool.map(translate, p["objects"]):
            print(f"\n=== {name} ===\n{sql}")
    pathlib.Path("migrated/plan.json").write_text(json.dumps(p, indent=2), encoding="utf-8")
    print("\ntokens:", usage)