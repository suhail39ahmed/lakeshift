"""LakeShift demo page: Oracle PL/SQL to Snowflake, proven row by row."""
import json, pathlib, subprocess, sys
import streamlit as st

M = pathlib.Path("migrated")
PRICE = {  # USD per 1M tokens (input, output), Nebius Token Factory
    "NVIDIA-Nemotron-3-Nano-30B-A3B": (0.06, 0.24),
    "nemotron-3-super-120b-a12b": (0.30, 0.90),
    "Nemotron-3-Ultra-550b-a55b": (1.00, 3.00),
}
LABEL = {"NVIDIA-Nemotron-3-Nano-30B-A3B": "Nano", "nemotron-3-super-120b-a12b": "Super",
         "Nemotron-3-Ultra-550b-a55b": "Ultra"}

st.set_page_config(page_title="LakeShift", page_icon="🌊", layout="wide")
st.title("🌊 LakeShift")
st.caption("Legacy Oracle PL/SQL to Snowflake SQL, translated by NVIDIA Nemotron on Nebius "
           "Token Factory and proven row by row against the original database.")

def load(name):
    p = M / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

# --- optional live run (only where the private Oracle is reachable, i.e. the laptop) ---
with st.sidebar:
    st.header("Run")
    st.write("The hosted page replays the last verified run. "
             "Live runs need the private Oracle database, which never leaves the laptop.")
    import socket
    try:
        socket.create_connection(("127.0.0.1", 1521), timeout=0.5).close(); oracle_here = True
    except OSError:
        oracle_here = False
    if not oracle_here:
        st.caption("Private Oracle not reachable from here, so live full runs are off.")
    if oracle_here and st.button("Run migration live", type="primary"):
        with st.status("Planning, translating, verifying...", expanded=True) as s:
            proc = subprocess.Popen([sys.executable, "-m", "lakeshift", "run"],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace")
            for line in proc.stdout:
                st.text(line.rstrip())
            s.update(label="Run finished" if proc.wait() == 0 else "Run failed",
                     state="complete" if proc.returncode == 0 else "error")

report, log, plan = load("report.json"), load("fix_log.json") or [], load("plan.json")
if not report:
    st.info("No run yet. Run `python -m lakeshift run` first.")
    st.stop()

# --- headline numbers ---
passed = sum(r["status"] == "PASS" for r in report.values())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Objects proven equal", f"{passed} / {len(report)}")
c2.metric("Rows compared", f"{sum(r.get('rows', 0) for r in report.values()):,}")
solved_by = {}
for name, r in report.items():
    fixes = [l["model"].split("/")[-1] for l in log if l["object"] == name]
    solved_by[name] = "first try" if not fixes else (LABEL.get(fixes[-1], fixes[-1])
                       if r["status"] == "PASS" else "unsolved")
c3.metric("Needed the big model (Ultra)", sum(v == "Ultra" for v in solved_by.values()))
c4.metric("Raw customer values sent to models", 0)

# --- scorecard ---
st.subheader("Scorecard")
rows = []
for name, r in report.items():
    rows.append({"object": name, "result": r["status"], "solved by": solved_by[name],
                 "rows": r.get("rows", r.get("rows_oracle", "")),
                 "sources cited": len({u for l in log if l["object"] == name
                                       for u in l.get("sources", [])})})
st.dataframe(rows, width='stretch', hide_index=True)

st.markdown("**Model ladder:** every object starts with the cheapest model (Nano). "
            "Only when the row-by-row proof fails does it move up to Super, then Ultra.")

# --- per-object detail ---
st.subheader("Look inside an object")
name = st.selectbox("Object", list(report))
obj = next((o for o in (plan or {}).get("objects", []) if o["name"] == name), None)
left, right = st.columns(2)
with left:
    st.markdown("**Oracle (legacy)**")
    if obj and pathlib.Path("legacy", obj["file"]).exists():
        st.code(pathlib.Path("legacy", obj["file"]).read_text(encoding="utf-8"), language="sql")
with right:
    st.markdown("**Snowflake (migrated)**")
    p = M / f"{name}.sql"
    if p.exists():
        st.code(p.read_text(encoding="utf-8"), language="sql")
attempts = [l for l in log if l["object"] == name]
if attempts:
    st.markdown("**Repair attempts**")
    for a in attempts:
        st.write(f"- {LABEL.get(a['model'].split('/')[-1], a['model'])}: {a['result']}")
    urls = sorted({u for a in attempts for u in a.get("sources", [])})
    if urls:
        st.markdown("**Official docs cited (via Tavily)**")
        for u in urls:
            st.markdown(f"- [{u.split('//')[-1][:90]}]({u})")
if obj and obj.get("risks"):
    st.markdown("**Migration risks the planner spotted**")
    for risk in obj["risks"]:
        st.write(f"- {risk}")

# --- live translation: a real Nemotron call on Nebius Token Factory ---
st.subheader("Try it live")
st.write("Paste a small Oracle snippet. Nemotron Nano translates it to Snowflake SQL right now "
         "(no database needed, costs a fraction of a cent).")
EXAMPLE = """SELECT customer_id,
       NVL(email, 'unknown@none') AS email,
       TRUNC(signup_date, 'MM') AS signup_month,
       DECODE(tier_code, 'G', 'GOLD', 'S', 'SILVER', 'BRONZE') AS tier
FROM raw_customers
WHERE ROWNUM <= 10"""
snippet = st.text_area("Oracle SQL / PL/SQL", EXAMPLE, height=180, max_chars=4000)
if st.button("Translate with Nemotron"):
    try:
        from lakeshift.llm import chat, NANO, usage
        from lakeshift.fixer import clean
        system = ("You translate Oracle SQL or PL/SQL to Snowflake SQL. Preserve Oracle semantics "
                  "exactly (in Oracle '' IS NULL). Return only the Snowflake SQL, no explanations.")
        with st.spinner("Calling NVIDIA Nemotron Nano on Nebius Token Factory..."):
            before = sum(usage.values())
            out = clean(chat(NANO, system, snippet)) or "(no SQL returned, try again)"
        st.code(out, language="sql")
        st.caption(f"{sum(usage.values()) - before:,} tokens used. This translation is not "
                   "verified; full runs prove every object against Oracle row by row.")
    except Exception as e:
        st.error(f"Live call unavailable: {e}")

# --- security ---
st.subheader("Security")
st.markdown("""
- The source Oracle database runs privately: bound to `127.0.0.1` on a private Docker network.
- Customer text values are masked before any model call; models only see shapes like `<text#a1b2c3 len=9 Mixed>`.
- Research is restricted to docs.oracle.com and docs.snowflake.com, and every source is logged.
- Serverless inference on Nebius Token Factory; a dedicated endpoint is the enterprise option for isolated capacity.
""")
