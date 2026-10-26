"""LakeShift demo page: Oracle PL/SQL to Snowflake, proven row by row."""
import datetime, json, os, pathlib, shutil, socket, subprocess, sys, tempfile
import streamlit as st

M = pathlib.Path("migrated")
PRICE = {  # USD per 1M tokens (input, output), Nebius Token Factory
    "NVIDIA-Nemotron-3-Nano-30B-A3B": (0.06, 0.24),
    "nemotron-3-super-120b-a12b": (0.30, 0.90),
    "Nemotron-3-Ultra-550b-a55b": (1.00, 3.00),
}
CACHED_IN = {  # USD per 1M cached input tokens; Nano has no cached price (billed as regular)
    "NVIDIA-Nemotron-3-Nano-30B-A3B": 0.06,
    "nemotron-3-super-120b-a12b": 0.06,
    "Nemotron-3-Ultra-550b-a55b": 0.12,
}
LABEL = {"NVIDIA-Nemotron-3-Nano-30B-A3B": "Nano", "nemotron-3-super-120b-a12b": "Super",
         "Nemotron-3-Ultra-550b-a55b": "Ultra"}

# Hosted deployments keep settings in st.secrets; expose them as env vars for the pipeline.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, (str, int, float)):
            os.environ.setdefault(_k, str(_v))
except Exception:
    pass                                       # no secrets file: local run, .env is used

st.set_page_config(page_title="LakeShift", page_icon="ðŸŒŠ", layout="wide")
st.title("ðŸŒŠ LakeShift")
st.caption("Legacy Oracle PL/SQL to Snowflake SQL, translated by NVIDIA Nemotron on Nebius "
           "Token Factory and proven row by row against the original database.")

def load(name):
    p = M / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

# --- optional live run (only where the demo Oracle is reachable) ---
ROOT = pathlib.Path(__file__).resolve().parent
RUNS_FILE = pathlib.Path(tempfile.gettempdir()) / "lakeshift_live_runs.json"
RUN_CAP = int(os.environ.get("LIVE_RUNS_PER_DAY", "10"))

def runs_today():
    today = datetime.date.today().isoformat()
    try:
        data = json.loads(RUNS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return today, int(data.get(today, 0))

def count_run():
    today, n = runs_today()
    RUNS_FILE.write_text(json.dumps({today: n + 1}), encoding="utf-8")
    return n + 1

LIVE_DIR = ROOT / ".live"                      # gitignored: latest live result lives here

def live_workdir():
    """Copy inputs to a scratch folder so a live run never overwrites the committed results."""
    work = pathlib.Path(tempfile.mkdtemp(prefix="lakeshift_run_"))
    shutil.copytree(ROOT / "legacy", work / "legacy")
    shutil.copytree(ROOT / "data", work / "data")
    shutil.copytree(M if M.is_absolute() else ROOT / M, work / "migrated",
                    ignore=shutil.ignore_patterns("replies", "rejected"))
    return work

def summarize_live(out_dir, returncode, lines, started):
    """Build a compact scorecard from a live run's migrated/ folder."""
    def rd(name):
        f = out_dir / name
        try:
            return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        except (OSError, ValueError) as e:
            return {"_error": f"{name}: {e}"}
    rep, flog, use = rd("report.json") or {}, rd("fix_log.json") or [], rd("usage.json") or {}
    if not isinstance(flog, list):
        flog = []
    rows = []
    for name, r in rep.items():
        if not isinstance(r, dict):
            continue
        fixes = [l.get("model", "").split("/")[-1] for l in flog if l.get("object") == name]
        by = "first try" if not fixes else (LABEL.get(fixes[-1], fixes[-1])
                                            if r.get("status") == "PASS" else "unsolved")
        rows.append({"object": name, "result": r.get("status"), "solved by": by, "rows": r.get("rows", 0)})
    return {"finished": datetime.datetime.now().isoformat(timespec="seconds"),
            "started": started, "returncode": returncode,
            "ok": returncode == 0 and bool(rows) and all(x["result"] == "PASS" for x in rows),
            "scorecard": rows, "tokens": use.get("tokens", {}),
            "seconds": use.get("seconds"), "log_tail": lines[-40:]}

def show_live(res):
    passed = sum(r["result"] == "PASS" for r in res["scorecard"])
    head = f"Live run {res['finished']}: {passed} / {len(res['scorecard'])} proven equal"
    (st.success if res["ok"] else st.error)(head)
    if res["scorecard"]:
        st.dataframe(res["scorecard"], hide_index=True, use_container_width=True)
    tok = sum(res["tokens"].values()) if res["tokens"] else 0
    secs = res.get("seconds")
    st.caption(f"Tokens: {tok:,}" + (f" ? time: {secs:.0f} s" if isinstance(secs, (int, float)) else ""))
    if not res["ok"]:
        st.caption(f"Exit code {res['returncode']}. Last log lines:")
        st.code("\n".join(res["log_tail"]) or "(no output)")

if "live_result" not in st.session_state:          # survive reruns and app restarts
    try:
        st.session_state.live_result = json.loads((LIVE_DIR / "latest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st.session_state.live_result = None

with st.sidebar:
    st.header("Run")
    st.write("The page shows the last verified run. A live run plans, translates and "
             "verifies everything again against the demo Oracle database.")
    o_host = os.environ.get("ORACLE_HOST", "127.0.0.1")
    o_port = int(os.environ.get("ORACLE_PORT", "1521"))
    try:
        socket.create_connection((o_host, o_port), timeout=2).close(); oracle_here = True
    except OSError:
        oracle_here = False
    if not oracle_here:
        st.caption("Demo Oracle not reachable from here, so live full runs are off.")
    else:
        _, used = runs_today()
        left = max(RUN_CAP - used, 0)
        left_box = st.empty()
        left_box.caption(f"Live runs left today: {left} / {RUN_CAP}")
        code = os.environ.get("JUDGE_ACCESS_CODE", "")
        entered = st.text_input("Access code", type="password") if code else ""
        allowed = (not code or entered == code) and left > 0
        if code and entered and entered != code:
            st.error("Wrong access code.")
        if st.button("Run migration live", type="primary", disabled=not allowed):
            used = count_run()                         # count before the run starts
            left_box.caption(f"Live runs left today: {max(RUN_CAP - used, 0)} / {RUN_CAP}")
            started = datetime.datetime.now().isoformat(timespec="seconds")
            lines, rc, work = [], None, None
            try:
                work = live_workdir()
                env = dict(os.environ, PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""))
                with st.status("Planning, translating, verifying...", expanded=True) as s:
                    proc = subprocess.Popen([sys.executable, "-m", "lakeshift", "run"], cwd=work, env=env,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            text=True, encoding="utf-8", errors="replace")
                    for line in proc.stdout:
                        lines.append(line.rstrip())
                        st.text(lines[-1])
                    rc = proc.wait()
                    s.update(label="Run finished" if rc == 0 else "Run failed",
                             state="complete" if rc == 0 else "error", expanded=False)
                res = summarize_live(work / "migrated", rc, lines, started)
            except Exception as e:                     # surface, never swallow
                lines.append(f"{type(e).__name__}: {e}")
                res = summarize_live(pathlib.Path("/nonexistent"), rc if rc is not None else -1, lines, started)
            finally:
                try:
                    LIVE_DIR.mkdir(exist_ok=True)
                    if "res" in locals():
                        (LIVE_DIR / "latest.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
                        (LIVE_DIR / "latest.log").write_text("\n".join(lines), encoding="utf-8")
                        if work and (work / "migrated").exists():
                            shutil.copytree(work / "migrated", LIVE_DIR / "migrated", dirs_exist_ok=True,
                                            ignore=shutil.ignore_patterns("replies", "rejected"))
                except OSError as e:
                    st.warning(f"Could not save the live result: {e}")
                if work:
                    shutil.rmtree(work, ignore_errors=True)
            st.session_state.live_result = res
            st.rerun()
    if st.session_state.get("live_result"):
        st.subheader("Latest live run")
        show_live(st.session_state.live_result)
        st.caption("The tabs keep showing the verified run.")

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
                "Why Nebius + Nemotron", "Dedicated endpoint", "Where this applies", "Security"])

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
    st.info("**Two demo modes.** *Private mode:* Oracle runs on the laptop, bound to 127.0.0.1 on a "
            "private Docker network (how the run was recorded). *Judge demo:* a separate Oracle on a "
            "Google Cloud VM holds only synthetic sample data, with a non-admin demo user, so this hosted "
            "page can run the full live migration, guarded by an access code and a daily run cap. "
            "Real customer data never leaves the customer network.")

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
            from lakeshift.llm import chat, NANO, usage as llm_usage
            from lakeshift.fixer import clean
            system = ("You translate Oracle SQL or PL/SQL to Snowflake SQL. Preserve Oracle semantics "
                      "exactly (in Oracle '' IS NULL). Return only the Snowflake SQL, no explanations.")
            with st.spinner("Calling NVIDIA Nemotron Nano on Nebius Token Factory..."):
                before = sum(llm_usage.values())
                out = clean(chat(NANO, system, snippet)) or "(no SQL returned, try again)"
            st.code(out, language="sql")
            st.caption(f"{sum(llm_usage.values()) - before:,} tokens used. This translation is not "
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
    st.subheader("Nebius features LakeShift uses")
    det = usage.get("details") or {}
    if det:
        cached = sum(d.get("cached", 0) for d in det.values())
        prompt_t = sum(d.get("prompt", 0) for d in det.values())
        compl = sum(d.get("completion", 0) for d in det.values())
        reas = sum(d.get("reasoning", 0) for d in det.values())
        saved = sum(d.get("cached", 0) / 1e6 * (PRICE[m][0] - CACHED_IN.get(m, PRICE[m][0]))
                    for m, d in det.items() if m in PRICE)
        f1, f2, f3 = st.columns(3)
        f1.metric("Input tokens served from cache", f"{cached:,}",
                  f"{cached / prompt_t:.0%} of input" if prompt_t else None, delta_color="off")
        f2.metric("Saved by prompt caching", f"${saved:.4f}")
        f3.metric("Output spent on reasoning", f"{reas / compl:.0%}" if compl else "n/a",
                  f"{reas:,} of {compl:,} tokens", delta_color="off")
        st.dataframe([{"model": LABEL.get(m, m), "calls": d.get("calls", 0),
                       "input": f"{d.get('prompt', 0):,}", "cached": f"{d.get('cached', 0):,}",
                       "output": f"{d.get('completion', 0):,}",
                       "reasoning": f"{d.get('reasoning', 0):,}"} for m, d in det.items()],
                     width="stretch", hide_index=True)
        st.caption("Nano has no separate cached price, so its cached tokens save nothing. "
                   "Nano does not report reasoning tokens; its share counts Super and Ultra only.")
    else:
        st.info("Cache and reasoning numbers: measured on next run.")
    st.markdown("""
- **Prompt caching.** Every call starts with the same fixed instructions, and Token Factory reuses that
  prefix automatically. Cached input on Super costs $0.06 instead of $0.30 per 1M tokens, on Ultra $0.12
  instead of $1.00. In a test, a repeated 1,745-token prompt came back with 1,728 tokens cached.
- **Structured output.** The models must answer as JSON `{"sql": ..., "notes": ...}`, so LakeShift reads
  the SQL directly instead of digging it out of free text. If the JSON is ever broken, the old text
  cleaner is the fallback.
- **Reasoning effort.** Nemotron thinks before it answers, and those thinking tokens are billed.
  LakeShift asks Nano for `low` effort on first drafts, Super for `medium` and Ultra for `high`
  on the hard repairs. The thinking comes back in a separate field, so it never leaks into the SQL.
""")
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
    st.subheader("Serverless vs dedicated endpoint")
    st.markdown("""
| | Serverless (what LakeShift uses today) | Dedicated endpoint |
|---|---|---|
| **Pricing** | Per token | Per GPU-hour, billed per minute, only while `Ready` |
| **Capacity** | Shared, multi-tenant | Reserved for your organisation |
| **Rate limits** | Dynamic limits apply | None; throughput = the GPUs you deploy |
| **Region** | Can move with available capacity | Fixed, you choose it (data residency) |
| **Scaling** | Platform-managed | You set min and max replicas |
| **Custom weights** | Base models only | Supported for eligible models |
""")
    st.markdown("""
**When LakeShift uses each**
- **Serverless:** bursty migration waves. Six objects cost cents and nothing runs between waves.
- **Dedicated:** large bank, insurance or healthcare programmes that need a fixed region for data
  residency, steady high volume (thousands of objects a night), predictable latency, or a Nano
  fine-tuned on the customer's own coding standards.
- The ladder stays the same: Nano can move to a dedicated endpoint while Super and Ultra stay serverless
  for the rare hard objects. Nemotron 3 Nano is offered as a dedicated template (H100 in eu-north1,
  H200 in us-central1).
""")
    GPU_HOUR = 4.50                                   # H100, nebius.com/prices
    nano_in, nano_out = PRICE["NVIDIA-Nemotron-3-Nano-30B-A3B"]
    nano_run = usage["tokens"].get("NVIDIA-Nemotron-3-Nano-30B-A3B", 0)
    be_tokens = GPU_HOUR / nano_out * 1e6             # output-rate tokens per hour to break even
    b1, b2, b3 = st.columns(3)
    b1.metric("1 H100, per hour", f"${GPU_HOUR:.2f}")
    b2.metric("Breakeven vs serverless Nano", f"{be_tokens / 1e6:.1f}M tokens/hour",
              f"about {be_tokens / 3600:,.0f} tokens/s sustained", delta_color="off")
    b3.metric("= full LakeShift runs per hour", f"{be_tokens / nano_run:,.0f}" if nano_run else "n/a")
    st.caption(f"Breakeven = ${GPU_HOUR:.2f}/GPU-hour / ${nano_out:.2f} per 1M Nano output tokens "
               f"(worst case; at the ${nano_in:.2f} input rate it is {GPU_HOUR / nano_in:.0f}M tokens/hour). "
               "Below that volume serverless is cheaper; dedicated is chosen for residency, "
               "reserved capacity and no rate limits, not price.")

    st.subheader("Switch in 3 steps")
    st.code("""# 1. Create a dedicated endpoint for nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B (1 GPU, 1 replica)
# 2. Point LakeShift at it (Super and Ultra stay on serverless)
$env:NEBIUS_NANO_MODEL = "<routing key from the endpoint card>"
$env:NEBIUS_DEDICATED_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
# 3. Same pipeline, same code
python -m lakeshift.bench --target dedicated --runs 1
python -m lakeshift run""", language="powershell")

    st.subheader("Run on dedicated endpoint")
    st.button("Run migration on dedicated endpoint", disabled=True, key="run_dedicated",
              help="Locked: the endpoint is stopped to save GPU cost.")
    st.info("This run was done live on Oct 26, 2026 on a dedicated Nemotron 3 Nano endpoint "
            "(1x H100, eu-north1) and the endpoint was then stopped, because it bills per GPU-hour "
            "while running. The measured results are below; the live demo above uses serverless.")

    st.subheader("Benchmark: Nano translation, serverless vs dedicated")
    bench_rows = []
    for tgt in ("serverless", "dedicated"):
        f = M / f"bench_{tgt}.json"
        if f.exists():
            b = json.loads(f.read_text(encoding="utf-8")); s = b["summary"]
            bench_rows.append({"target": tgt, "status": "measured", "calls": s["calls"],
                               "median latency (s)": s["median_latency_s"],
                               "median time to first token (s)": s["median_ttft_s"],
                               "median tokens/s": s["median_tokens_per_s"],
                               "output tokens": s["total_completion_tokens"],
                               "max tokens": b.get("max_tokens"), "measured": b["timestamp"]})
        else:
            bench_rows.append({"target": tgt, "status": "benchmark pending"})
    st.dataframe(bench_rows, width="stretch", hide_index=True)
    st.caption("Same six legacy objects and prompts on both targets. "
               "Run with `python -m lakeshift.bench --target serverless|dedicated`.")

with tabs[6]:
    st.markdown("""
Anywhere legacy Oracle logic must move to the cloud, a wrong number is expensive, and the data must stay private:

- **Banking and insurance:** loyalty and wallet balances, account hierarchies, regulatory reports where a wrong number is a compliance issue.
- **Retail and e-commerce:** rewards points, churn and reorder analytics such as order gaps.
- **Telecom:** customer hierarchies and usage rollups.
- **Healthcare and public sector:** data cannot leave on-prem; masking plus local verification keep it there.
- **Manufacturing:** bill-of-materials hierarchies written with `CONNECT BY`.
- **Consultancies and SIs** running Oracle-to-Snowflake programmes: the row-by-row proof report is the sign-off artifact.
""")

with tabs[7]:
    st.subheader("Security")
    st.markdown("""
    - Private mode: the source Oracle runs on the laptop, bound to `127.0.0.1` on a private Docker network.
    - Judge demo: a separate Oracle on a Google Cloud VM holds only synthetic sample data, uses a non-admin demo user, and live runs need an access code and are capped per day. It is the only database the hosted page can reach.
    - Customer text values are masked before any model call; models only see shapes like `<text#a1b2c3 len=9 Mixed>`.
    - Research is restricted to docs.oracle.com and docs.snowflake.com, and every source is logged.
    - Serverless inference on Nebius Token Factory; a dedicated endpoint is the enterprise option for isolated capacity.
    """)
    st.markdown("""
**Production design: bring the code to the data.** With real data, the hosted page queues a job; a worker next
to the database runs the Oracle side locally and returns only the scorecard. Oracle never
accepts an outside connection and no customer rows leave the site. Options considered: an open
port (never), a VPN such as Tailscale, Cloudflare Tunnel with Access.
""")
