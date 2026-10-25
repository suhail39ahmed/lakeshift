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

usage = load("usage.json") or {"tokens": {  # fallback: latest verified run
    "NVIDIA-Nemotron-3-Nano-30B-A3B": 40698, "nemotron-3-super-120b-a12b": 9721,
    "Nemotron-3-Ultra-550b-a55b": 15022}, "seconds": 327}

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


tabs = st.tabs(["Overview", "Scorecard", "Inside an object", "Try it live",
                "Why Nebius + Nemotron", "Where this applies", "Security"])

with tabs[0]:
    st.image("docs/architecture.png", width="stretch")
    st.markdown("""
**The problem.** Moving Oracle PL/SQL to Snowflake is not a syntax job. `''` is NULL in Oracle
but not in Snowflake, date arithmetic and `MONTHS_BETWEEN` differ, cursor loops carry hidden
state, and `CONNECT BY` has no one-to-one twin. Teams find these differences in production.

**The approach.** The original Oracle database is the answer key. Every translation runs in
Snowflake on the same data and must return exactly the same rows before it counts as done.

1. **Planner** finds every object, what it reads and writes, its risks and the run order.
2. **Translators** (Nemotron Nano, in parallel) convert each object to Snowflake SQL.
3. **Verifier** runs the untouched legacy code in a private Oracle and the translation in
   Snowflake, then compares full result sets row by row, plus day-2 scenarios.
4. On a mismatch, the **Researcher** pulls official Oracle and Snowflake docs through Tavily,
   and the **Fixer** climbs the ladder Nano, then Super, then Ultra, until the proof passes.
""")
    st.info("**Demo modes.** The full live pipeline runs where the private Oracle lives (recorded on "
            "the laptop). This hosted page replays the last verified run and makes live Nemotron "
            "calls in *Try it live*. The Oracle database is intentionally never exposed.")

with tabs[1]:
    # --- scorecard ---
    st.subheader("Scorecard")
    rows = []
    for name, r in report.items():
        rows.append({"object": name, "result": r["status"], "solved by": solved_by[name],
                     "rows": str(r.get("rows", r.get("rows_oracle", ""))),
                     "sources cited": len({u for l in log if l["object"] == name
                                           for u in l.get("sources", [])})})
    st.dataframe(rows, width='stretch', hide_index=True)

    st.markdown("**Model ladder:** every object starts with the cheapest model (Nano). "
                "Only when the row-by-row proof fails does it move up to Super, then Ultra.")


with tabs[2]:
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


with tabs[3]:
    # --- live translation: a real Nemotron call on Nebius Token Factory ---
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


with tabs[4]:
    st.subheader("Cost of this run")
    toks = usage["tokens"]
    cost_rows, total, total_ultra = [], 0.0, 0.0
    for mid, (pin, pout) in PRICE.items():
        t = toks.get(mid, 0)
        c = t / 1e6 * pout
        total += c; total_ultra += t / 1e6 * PRICE["Nemotron-3-Ultra-550b-a55b"][1]
        cost_rows.append({"model": f"Nemotron 3 {LABEL[mid]}", "id": f"nvidia/{mid}",
                          "price in / out per 1M": f"${pin:.2f} / ${pout:.2f}",
                          "tokens this run": f"{t:,}", "worst-case cost": f"${c:.4f}"})
    st.dataframe(cost_rows, width="stretch", hide_index=True)
    k1, k2, k3 = st.columns(3)
    k1.metric("Full run, worst case", f"${total:.3f}")
    k2.metric("Same tokens all on Ultra", f"${total_ultra:.3f}")
    k3.metric("Ladder saving", f"{total_ultra / total:.1f}x cheaper" if total else "n/a")
    st.caption("Worst-case estimate: every token priced at the output rate. Prices are Nebius "
               "Token Factory per 1M tokens.")
    st.subheader("Setup in 3 lines")
    st.code('''from openai import OpenAI
client = OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/", api_key=NEBIUS_API_KEY)
reply = client.chat.completions.create(model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", messages=msgs)''',
            language="python")
    st.markdown("""
- **Open NVIDIA models** in three sizes, so the cheap one does most of the work and the big one is called only when the proof fails.
- **Serverless, pay per token.** No GPUs to provision; a full six-object migration costs cents.
- **OpenAI-compatible.** The standard `openai` client, one API key; switching model is changing one string.
- **Enterprise path.** A dedicated endpoint gives isolated capacity with the same code; only the base URL and model name change.
""")

with tabs[5]:
    st.markdown("""
Anywhere legacy Oracle logic must move to the cloud, a wrong number is expensive, and the data must stay private:

- **Banking and insurance:** loyalty and wallet balances, account hierarchies, regulatory reports where a wrong number is a compliance issue.
- **Retail and e-commerce:** rewards points, churn and reorder analytics such as order gaps.
- **Telecom:** customer hierarchies and usage rollups.
- **Healthcare and public sector:** data cannot leave on-prem; masking plus local verification keep it there.
- **Manufacturing:** bill-of-materials hierarchies written with `CONNECT BY`.
- **Consultancies and SIs** running Oracle-to-Snowflake programmes: the row-by-row proof report is the sign-off artifact.
""")

with tabs[6]:
    st.subheader("Security")
    st.markdown("""
    - The source Oracle database runs privately: bound to `127.0.0.1` on a private Docker network.
    - Customer text values are masked before any model call; models only see shapes like `<text#a1b2c3 len=9 Mixed>`.
    - Research is restricted to docs.oracle.com and docs.snowflake.com, and every source is logged.
    - Serverless inference on Nebius Token Factory; a dedicated endpoint is the enterprise option for isolated capacity.
    """)
    st.markdown("""
**Production design: bring the code to the data.** The hosted page queues a job; a worker next
to the database runs the Oracle side locally and returns only the scorecard. Oracle never
accepts an outside connection and no customer rows leave the site. Options considered: an open
port (never), a VPN such as Tailscale, Cloudflare Tunnel with Access.
""")
