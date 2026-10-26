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
    def _export(items):
        for _k, _v in items:
            if isinstance(_v, (str, int, float)):
                os.environ.setdefault(_k, str(_v))
            elif hasattr(_v, 'items'):            # keys that ended up under a [section]
                _export(_v.items())
    _export(st.secrets.items())
except Exception:
    pass                                       # no secrets file: local run, .env is used

st.set_page_config(page_title="LakeShift", page_icon="🌊", layout="wide", initial_sidebar_state="collapsed")
STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono&display=swap');
:root { --ink:#0F172A; --mut:#475569; --line:#E5E7EB; --ind:#4F46E5; --cy:#06B6D4; --soft:#F5F7FB; }
html { scroll-behavior:smooth; }
.stApp { background:#FFFFFF; color:var(--ink); font-family:'Inter',sans-serif; font-size:16px; }
.stApp::before, .stApp::after { content:""; position:fixed; z-index:0; pointer-events:none; border-radius:50%;
  filter:blur(100px); width:560px; height:560px; }
.stApp::before { background:rgba(79,70,229,.10); top:-160px; left:-120px; animation:ls-orb1 24s ease-in-out infinite alternate; }
.stApp::after { background:rgba(6,182,212,.10); bottom:-180px; right:-140px; animation:ls-orb2 28s ease-in-out infinite alternate; }
@keyframes ls-orb1 { to { transform:translate(35vw,25vh) scale(1.15); } }
@keyframes ls-orb2 { to { transform:translate(-30vw,-35vh) scale(.9); } }
[data-testid="stMain"], section.main { position:relative; z-index:1; }
.block-container { max-width:1200px; padding-top:2.2rem; padding-bottom:3rem; }
header[data-testid="stHeader"] { background:rgba(255,255,255,.7) !important; backdrop-filter:blur(8px); }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { color:var(--ink); font-weight:800; letter-spacing:-.01em; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color:var(--mut) !important; }
code, pre { font-family:'JetBrains Mono',monospace !important; }
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within {
  border-color:var(--ind) !important; box-shadow:0 0 0 3px rgba(79,70,229,.18) !important; }
@keyframes ls-in { from {opacity:0; transform:translateY(14px);} to {opacity:1; transform:none;} }
@property --ls-a { syntax:'<angle>'; initial-value:0deg; inherits:false; }
@keyframes ls-spin { to { --ls-a:360deg; } }
@keyframes ls-pulse { 0%,100%{box-shadow:0 0 0 0 rgba(79,70,229,.35)} 50%{box-shadow:0 0 0 10px rgba(79,70,229,0)} }
.ls-hero { padding:34px 38px; border-radius:22px; margin:0 0 22px;
  background:linear-gradient(#FFFFFF,#FFFFFF) padding-box,
             conic-gradient(from var(--ls-a), #4F46E5, #06B6D4, #E0E7FF, #4F46E5) border-box;
  border:2px solid transparent; animation:ls-in .8s ease-out both, ls-spin 8s linear infinite;
  box-shadow:0 18px 50px rgba(15,23,42,.08); }
.ls-ribbon { display:inline-block; padding:6px 14px; border-radius:999px; font-size:.82rem; font-weight:700;
  color:#FFFFFF; background:linear-gradient(90deg,#4F46E5,#06B6D4); }
.ls-hero h1 { margin:14px 0 0; font-size:3.3rem; font-weight:900; letter-spacing:-.03em; color:var(--ink); line-height:1.05; }
.ls-g { background:linear-gradient(90deg,#4F46E5,#06B6D4); -webkit-background-clip:text; background-clip:text; color:transparent; }
.ls-hero p.ls-tag { margin:.6rem 0 0; font-size:1.12rem; color:var(--mut); max-width:900px; }
.ls-hero p.ls-who { margin:.6rem 0 0; font-weight:700; color:var(--ink); }
.ls-badges span { display:inline-block; margin:14px 8px 0 0; padding:5px 12px; border-radius:999px; font-size:.8rem;
  background:#EEF2FF; border:1px solid #C7D2FE; color:#3730A3; }
.ls-foot { margin:56px 0 10px; padding:20px; text-align:center; border-top:1px solid var(--line); color:var(--mut); }
.ls-foot b { color:var(--ink); }
.ls-card { background:#FFFFFF; border:1px solid var(--line); border-radius:18px; padding:22px 24px; margin:10px 0 18px;
  box-shadow:0 8px 24px rgba(15,23,42,.05); transition:transform .25s, box-shadow .25s, border-color .25s; animation:ls-in .5s ease-out both; }
.ls-card:hover { transform:translateY(-4px); border-color:#C7D2FE; box-shadow:0 16px 36px rgba(79,70,229,.14); }
.ls-card h4 { margin:0 0 8px; } .ls-card ul { margin:0; padding-left:0; list-style:none; }
.ls-card li { margin:8px 0; padding-left:28px; position:relative; color:var(--ink); }
.ls-card li::before { content:"\\2714"; position:absolute; left:0; color:#4F46E5; font-weight:900; }
.ls-pass { display:inline-block; padding:2px 10px; border-radius:999px; background:#ECFCCB; color:#3F6212; font-weight:700; border:1px solid #76B900; }
[data-testid="stMetric"] { background:#FFFFFF; border:1px solid var(--line); border-radius:18px; padding:18px 20px;
  box-shadow:0 8px 24px rgba(15,23,42,.05); transition:transform .25s, box-shadow .25s, border-color .25s; animation:ls-in .6s ease-out both; }
[data-testid="stMetric"]:hover { transform:translateY(-5px); border-color:#A5B4FC; box-shadow:0 16px 34px rgba(79,70,229,.16); }
[data-testid="stMetricLabel"] * { color:var(--mut) !important; font-weight:600; }
[data-testid="stMetricValue"] { color:var(--ink) !important; font-weight:800; }
div.st-key-section [role="radiogroup"] { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:8px 0 22px; }
div.st-key-section [role="radiogroup"] > label { margin:0; padding:18px 16px; border-radius:16px; background:#FFFFFF;
  border:1.5px solid var(--line); box-shadow:0 6px 18px rgba(15,23,42,.05); cursor:pointer; justify-content:center;
  transition:transform .2s, box-shadow .2s, border-color .2s, background .2s; }
div.st-key-section [role="radiogroup"] > label:hover { transform:translateY(-3px); border-color:#A5B4FC; box-shadow:0 12px 28px rgba(79,70,229,.14); }
div.st-key-section [role="radiogroup"] > label > div:first-child { display:none; }
div.st-key-step [role="radiogroup"] { display:flex; flex-wrap:wrap; gap:10px; margin:6px 0 4px; }
div.st-key-step [role="radiogroup"] > label { margin:0; padding:8px 16px; border-radius:999px; border:1.5px solid #E5E7EB; background:#FFFFFF; cursor:pointer; transition:transform .2s, border-color .2s, background .2s; }
div.st-key-step [role="radiogroup"] > label > div:first-child { display:none; }
div.st-key-step [role="radiogroup"] > label:hover { transform:translateY(-2px); border-color:#A5B4FC; }
div.st-key-step [role="radiogroup"] > label:has(input:checked) { background:linear-gradient(90deg,#4F46E5,#06B6D4); border-color:transparent; }
div.st-key-step [role="radiogroup"] > label:has(input:checked) p { color:#FFFFFF; }
div.st-key-step [role="radiogroup"] > label p { font-weight:600; color:#0F172A; }
.ls-warn { display:inline-block; padding:2px 10px; border-radius:999px; background:#FEF3C7; color:#92400E; border:1px solid #F59E0B; font-weight:700; }
.ls-chip { display:inline-block; padding:2px 10px; border-radius:999px; background:#EEF2FF; color:#3730A3; border:1px solid #C7D2FE; font-weight:600; }
.ls-fail { display:inline-block; padding:2px 10px; border-radius:999px; background:#FEE2E2; color:#991B1B; border:1px solid #FCA5A5; font-weight:700; }
div.st-key-section [role="radiogroup"] > label p { font-size:1.02rem; font-weight:700; color:var(--ink); text-align:center; }
div.st-key-section [role="radiogroup"] > label:has(input:checked) { border-color:#4F46E5; background:#EEF2FF;
  transform:translateY(-3px); box-shadow:0 0 0 3px rgba(79,70,229,.15), 0 14px 30px rgba(6,182,212,.15); }
div.st-key-section [role="radiogroup"] > label:has(input:checked) p { color:#3730A3; }
.stTabs [data-baseweb="tab-list"] { gap:6px; padding:5px; border-radius:999px; background:var(--soft); width:fit-content; }
.stTabs [data-baseweb="tab"] { border-radius:999px !important; padding:6px 16px !important; height:auto; }
.stTabs [aria-selected="true"] { background:#FFFFFF !important; box-shadow:0 2px 8px rgba(15,23,42,.1); }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none !important; }
.stTabs [data-baseweb="tab-panel"] { animation:ls-in .45s ease-out both; padding-top:16px; }
[data-testid="stImage"] { overflow:hidden; border-radius:18px; box-shadow:0 14px 40px rgba(15,23,42,.10); border:1px solid var(--line); }
[data-testid="stImage"] img { transition:transform .5s cubic-bezier(.2,.8,.2,1); }
[data-testid="stImage"]:hover img { transform:scale(1.04); }
.stButton > button { position:relative; overflow:hidden; border-radius:12px; font-weight:700; padding:.65rem 1.1rem;
  border:1px solid #C7D2FE; transition:transform .2s, box-shadow .2s; }
.stButton > button::after { content:""; position:absolute; top:0; left:-120%; width:60%; height:100%;
  background:linear-gradient(120deg,transparent,rgba(255,255,255,.55),transparent); transition:left .6s; }
.stButton > button:hover:enabled::after { left:130%; }
.stButton > button:hover:enabled { transform:translateY(-2px); box-shadow:0 10px 24px rgba(79,70,229,.22); }
.stButton > button[kind="primary"] { background:linear-gradient(90deg,#4F46E5,#06B6D4); border:none; color:#FFFFFF; }
.stButton > button[kind="primary"]:enabled { animation:ls-pulse 2.6s infinite; }
.stButton > button:disabled { opacity:.5; }
[data-testid="stDataFrame"], [data-testid="stTable"] { border-radius:14px; overflow:hidden; border:1px solid var(--line);
  box-shadow:0 6px 20px rgba(15,23,42,.05); }
[data-testid="stAlert"], [data-testid="stExpander"] { border-radius:14px !important; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation:none !important; transition:none !important; scroll-behavior:auto !important; }
}
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)
CREDIT = "Built for the Nebius x NVIDIA Hackathon 2026"
st.markdown(
    '<div class="ls-hero"><span class="ls-ribbon">\U0001f3c6 ' + CREDIT + '</span>'
    '<h1>\U0001f30a Lake<span class="ls-g">Shift</span></h1>'
    '<p class="ls-tag">Legacy Oracle PL/SQL to Snowflake SQL, translated by NVIDIA Nemotron on Nebius '
    'Token Factory and proven row by row against the original database.</p>'
    '<p class="ls-who">Participant: Suhail Ahmed</p>'
    '<div class="ls-badges"><span>Nemotron Nano \u00b7 Super \u00b7 Ultra</span><span>Nebius Token Factory</span>'
    '<span>Row-by-row proof</span><span>Zero raw values to the model</span></div></div>',
    unsafe_allow_html=True)

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
    st.caption(f"Tokens: {tok:,}" + (f" \u00b7 time: {secs:.0f} s" if isinstance(secs, (int, float)) else ""))
    if not res["ok"]:
        st.caption(f"Exit code {res['returncode']}. Last log lines:")
        st.code("\n".join(res["log_tail"]) or "(no output)")

if "live_result" not in st.session_state:          # survive reruns and app restarts
    try:
        st.session_state.live_result = json.loads((LIVE_DIR / "latest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st.session_state.live_result = None

PROGRESS_FILE = pathlib.Path(tempfile.gettempdir()) / "lakeshift_progress.json"
RUN_LOG = pathlib.Path(tempfile.gettempdir()) / "lakeshift_run.log"

def read_progress():
    try:
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

def active_run():
    """Progress of a run that still holds the lock, or None (stale locks are cleared)."""
    from lakeshift.__main__ import lock_info
    try:
        if not lock_info():
            return None
    except Exception:
        return None
    return read_progress() or {"percent": 0, "message": "Starting", "events": [],
                               "started": __import__("time").time()}

def fmt_secs(s):
    s = max(int(s), 0)
    return f"{s // 60} min {s % 60} s" if s >= 60 else f"{s} s"

def eta_label(pr):
    import time as _t
    pct = max(int(pr.get("percent", 0)), 0)
    elapsed = _t.time() - float(pr.get("started", _t.time()))
    typical = (load("usage.json") or {}).get("seconds") or 240
    if pct >= 100:
        left = 0
    elif pct >= 10:
        left = elapsed * (100 - pct) / pct
    else:
        left = max(typical - elapsed, 15)
    return pct, elapsed, left

def show_progress(pr, bar, feed):
    pct, elapsed, left = eta_label(pr)
    msg = pr.get("message", "Working")
    tail = "done" if pct >= 100 else f"{fmt_secs(elapsed)} elapsed"
    bar.progress(min(pct, 100) / 100, text=f"{msg}: {pct}% ({tail})")
    ev = pr.get("events", [])[-14:]
    feed.markdown("<div style='background:#f7f9fc;border:1px solid #e3e8ef;border-radius:10px;"
                  "padding:10px 14px;font-size:.9rem;line-height:1.6'>" +
                  "".join(f"<div><span style='color:#8a94a6'>{fmt_secs(t)}</span>&nbsp; {html_escape(x)}</div>"
                          for t, x in ev) + "</div>", unsafe_allow_html=True)

def html_escape(x):
    import html as _h
    return _h.escape(str(x))

def show_other_run(pr):
    pct, elapsed, left = eta_label(pr)
    st.info(f"A live run is already in progress: {pct}% done, started {fmt_secs(elapsed)} ago, "
            f"Its results will appear here when it finishes.")
    show_progress(pr, st.empty(), st.empty())
    try:
        lines = RUN_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-6:]
        if lines:
            st.code("\n".join(lines))
    except OSError:
        pass
    if st.button("Refresh", key="refresh_run"):
        st.rerun()

def run_live(env, left_box):
    """Full live run (plan, translate, verify) in a temp copy; env picks serverless or dedicated."""
    used = count_run()                         # count before the run starts
    left_box.caption(f"Live runs left today: {max(RUN_CAP - used, 0)} / {RUN_CAP}")
    started = datetime.datetime.now().isoformat(timespec="seconds")
    lines, rc, work = [], None, None
    try:
        work = live_workdir()
        env = dict(env, PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""))
        bar, feed = st.empty(), st.empty()
        show_progress({"percent": 0, "message": "Starting run", "events": [[0, "Started run"]],
                       "started": __import__("time").time()}, bar, feed)
        with st.status("Full log", expanded=False) as s:
            # Output goes to a file, never a pipe: if this page is refreshed or closed,
            # the run can still write and finish instead of blocking on a full pipe.
            out_path = work / "run_output.log"
            out = open(out_path, "w", encoding="utf-8")
            proc = subprocess.Popen([sys.executable, "-u", "-m", "lakeshift", "run"], cwd=work, env=env,
                                    stdout=out, stderr=subprocess.STDOUT)
            out.close()
            log_box = st.empty()                   # one box, not one element per line
            reader = open(out_path, "r", encoding="utf-8", errors="replace")
            while True:
                done = proc.poll() is not None
                new = reader.read()
                if new:
                    lines.extend(l.rstrip() for l in new.splitlines() if l.strip())
                    log_box.code("\n".join(lines[-40:]))
                pr = read_progress()
                if pr and pr.get("pid") == proc.pid:
                    show_progress(pr, bar, feed)
                if done:
                    break
                __import__("time").sleep(1.5)
            reader.close()
            rc = proc.wait()
            if rc == 3 and any("already running" in l for l in lines):
                st.session_state["busy_note"] = True
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
        if work and ("proc" not in locals() or proc.poll() is not None):   # never pull files from a running run
            shutil.rmtree(work, ignore_errors=True)
    st.session_state.live_result = res
    st.rerun()

o_host = os.environ.get("ORACLE_HOST", "127.0.0.1")
o_port = int(os.environ.get("ORACLE_PORT", "1521"))
try:
    socket.create_connection((o_host, o_port), timeout=2).close(); oracle_here = True
except OSError:
    oracle_here = False
DED_VARS = ("NEBIUS_NANO_MODEL", "NEBIUS_DEDICATED_BASE_URL")
ded_ready = bool(os.environ.get("NEBIUS_DEDICATED_BASE_URL")) and \
    os.environ.get("NEBIUS_NANO_MODEL", "").startswith("dedicated/")

def run_panel():
    st.markdown("### \U0001f680 Run it live")
    st.write("The page shows the last verified run. A live run plans, translates and "
             "verifies everything again against the demo Oracle database.")
    if not oracle_here:
        st.caption("Demo Oracle not reachable from here, so live full runs are off.")
        st.session_state["peek_ok"] = not os.environ.get("JUDGE_ACCESS_CODE", "")
        b1, b2 = st.columns(2)
        b1.button("Run live migration", type="primary", disabled=True, width="stretch")
        b2.button("Run live migration on dedicated", disabled=True, width="stretch")
    else:
        _, used = runs_today()
        left = max(RUN_CAP - used, 0)
        code = os.environ.get("JUDGE_ACCESS_CODE", "")
        entered = st.text_input("Access code", type="password") if code else ""
        left_box = st.empty()
        left_box.caption(f"Live runs left today: {left} / {RUN_CAP}")
        allowed = (not code or entered == code) and left > 0
        st.session_state["peek_ok"] = not code or entered == code
        if code and entered and entered != code:
            st.error("Wrong access code.")
        other = active_run()
        if other:
            allowed = False
        elif st.session_state.pop("busy_check", False) or st.session_state.pop("busy_note", False):
            try:                                   # a run finished in another session: show its result
                st.session_state.live_result = json.loads((LIVE_DIR / "latest.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        b1, b2 = st.columns(2)
        go_srv = b1.button("Run live migration", type="primary", disabled=not allowed, width="stretch")
        go_ded = b2.button("Run live migration on dedicated", type="primary" if ded_ready else "secondary",
                           disabled=not (allowed and ded_ready), width="stretch", key="run_live_dedicated")
        if other:
            st.session_state["busy_check"] = True
            show_other_run(other)
        if ded_ready:
            b2.caption("Dedicated endpoint connected: Nano runs on the dedicated H100; Super and Ultra stay serverless.")
        else:
            b2.caption("Dedicated endpoint is stopped to save GPU cost. It was run live on Oct 26, 2026 "
                       "(1x H100): 307 vs 124 tokens/s. See Nebius > Dedicated endpoint.")
        if go_srv:
            run_live({k: v for k, v in os.environ.items() if k not in DED_VARS}, left_box)
        if go_ded:
            run_live(dict(os.environ), left_box)
    if st.session_state.get("live_result"):
        st.markdown("#### Latest live run")
        show_live(st.session_state.live_result)
        st.caption("The scorecard below keeps showing the verified run.")

def _peek_side(kind, table):
    """Read-only peek: a row count and the first 10 rows, ordered by the first column."""
    import re as _re
    if not _re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError("invalid table name")
    q = '"' + table.upper() + '"'
    if kind == "oracle":
        from lakeshift.oracle_ref import connect as _connect
        first = f"SELECT * FROM {q} ORDER BY 1 FETCH FIRST 10 ROWS ONLY"
    else:
        from lakeshift.warehouse import connect as _connect
        first = f"SELECT * FROM {q} ORDER BY 1 LIMIT 10"
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {q}")
        n = int(cur.fetchone()[0])
        cur.execute(first)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return {"count": n, "rows": rows}
    finally:
        conn.close()

def peek_panel(tables):
    st.markdown("### \U0001f50d Peek at both databases")
    st.write("Pick a table the migration writes and load it from both sides: the original Oracle and the migrated Snowflake.")
    ok = st.session_state.get("peek_ok", not os.environ.get("JUDGE_ACCESS_CODE", ""))
    t = st.selectbox("Target table", tables, key="peek_table", disabled=not ok or not tables)
    go = st.button("Load", key="peek_load", disabled=not ok or not tables)
    if not ok:
        st.caption("Enter the access code above to peek at the live databases")
        return
    if go and t in tables:
        res = {}
        for kind in ("oracle", "snowflake"):
            try:
                res[kind] = _peek_side(kind, t)
            except Exception as e:                     # never show connection details
                res[kind] = {"error": type(e).__name__}
        st.session_state["peek"] = {"table": t, **res}
    pk = st.session_state.get("peek")
    if not pk:
        return
    o, w = pk.get("oracle", {}), pk.get("snowflake", {})
    if "count" in o and "count" in w:
        same = o["count"] == w["count"]
        st.markdown(f'<span class="{"ls-pass" if same else "ls-warn"}">{"PASS: row counts match" if same else "Row counts differ"}</span>'
                    f' &nbsp; <span class="ls-chip">{pk["table"]}</span>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    for col, title, side in ((c1, "Oracle (source, Google Cloud)", o), (c2, "Snowflake (migrated)", w)):
        with col:
            st.markdown(f"#### {title}")
            if "error" in side:
                st.warning(f"Could not reach this database right now ({side['error']}).")
            else:
                st.metric("Rows", f"{side['count']:,}")
                st.dataframe(side["rows"], hide_index=True, width="stretch")

with st.sidebar:
    st.markdown("### \U0001f30a LakeShift")
    st.write("Oracle PL/SQL to Snowflake, translated by NVIDIA Nemotron on Nebius and proven row by row.")
    st.caption(CREDIT + " \u00b7 Participant: Suhail Ahmed")

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


SECTIONS = ["\U0001f680 Run & Results", "\U0001f9e9 How it works", "\u2601\ufe0f Nebius", "\U0001f6e1\ufe0f Trust"]
section = st.radio("Section", SECTIONS, horizontal=True, key="section", label_visibility="collapsed")

if section == SECTIONS[0]:
    with st.container(border=True):
        run_panel()
    _peek_tables = sorted({w for o in (plan or {}).get("objects", []) for w in (o.get("writes") or o.get("targets") or [])})
    with st.container(border=True):
        peek_panel(_peek_tables)
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

if section == SECTIONS[1]:
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
    st.markdown("### Follow one migration, step by step")
    _ex = next(iter(report)) if report else ""
    _hard = next((n for n, v in solved_by.items() if v == "Ultra"), next((n for n, v in solved_by.items() if v != "first try"), _ex))
    _hl = [l for l in log if l["object"] == _hard]
    _src = sorted({u for l in _hl for u in l.get("sources", [])})
    _pobjs = (plan or {}).get("objects", [])
    _order = " \u2192 ".join(o["name"] for o in _pobjs) or ", ".join(report)
    _first = sum(v == "first try" for v in solved_by.values())
    _rows = sum(r.get("rows", 0) or 0 for r in report.values() if isinstance(r.get("rows", 0), (int, float)))
    _risk = next((f"{o['name']}: {o['risks'][0]}" for o in _pobjs if o.get("risks")), "none recorded")
    STEP_TXT = {
        "1 \u00b7 Plan": ("The planner reads every legacy file, works out which objects depend on which, and lists the risky Oracle features.",
                     f"Order chosen this run: {_order}. Example risk it flagged: {_risk}."),
        "2 \u00b7 Translate with Nano": ("Nemotron Nano, the small fast model, drafts a Snowflake version of every object in parallel.",
                     f"{_first} of {len(report)} objects were correct straight away, with no repair needed."),
        "3 \u00b7 Verify": ("Both versions run on the same data: the original in Oracle, the new one in Snowflake. The results are compared.",
                     f"{_rows:,} rows were compared across all objects in the verified run."),
        "4 \u00b7 Research with Tavily docs": ("When a result differs, a researcher looks up the exact feature in the official Oracle and Snowflake docs.",
                     f"For {_hard}, it cited {len(_src)} official pages" + (f", for example {_src[0]}" if _src else "") + "."),
        "5 \u00b7 Fix ladder: Super, then Ultra": ("The repair goes to a bigger model only when the smaller one fails, so cost stays low.",
                     f"{_hard} took {len(_hl)} repair attempt(s): " + (", ".join(f"{LABEL.get(a['model'].split('/')[-1], a['model'])} {a['result']}" for a in _hl) or "none") + "."),
        "6 \u00b7 Prove row by row": ("Nothing counts as done until every row matches the original, including updates and deletes on day two.",
                     f"Final result: {passed} of {len(report)} objects proven equal."),
    }
    step = st.radio("Step", list(STEP_TXT), horizontal=True, key="step", label_visibility="collapsed")
    _what, _real = STEP_TXT[step]
    st.markdown(f'<div class="ls-card"><h4>{step}</h4><p>{_what}</p><p><b>In the real run:</b> {_real}</p></div>',
                unsafe_allow_html=True)
    st.divider()
    # --- per-object detail ---
    st.subheader("Look inside an object")
    name = st.selectbox("Object", list(report))
    obj = next((o for o in (plan or {}).get("objects", []) if o["name"] == name), None)
    _r = report.get(name, {})
    _ok = _r.get("status") == "PASS"
    st.markdown(f'<span class="{"ls-pass" if _ok else "ls-fail"}">{_r.get("status", "?")}</span> &nbsp; '
                f'<span class="ls-chip">Solved by: {solved_by.get(name, "?")}</span> &nbsp; '
                f'<span class="ls-chip">Rows compared: {_r.get("rows", _r.get("rows_oracle", "n/a"))}</span>',
                unsafe_allow_html=True)
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

if section == SECTIONS[2]:
    n_tabs = st.tabs(["Why Nebius + Nemotron", "Try it live", "Dedicated endpoint"])
    with n_tabs[0]:
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
        st.subheader("\U0001f9ee Cost calculator")
        _objs = st.slider("Objects to migrate", 1, 2000, 200, key="calc_objs")
        _runs = st.slider("Full verification runs per month", 1, 60, 4, key="calc_runs")
        _tok_obj = sum(usage["tokens"].values()) / max(len(report), 1)
        _cost_obj = sum(t / 1e6 * PRICE[m][1] for m, t in usage["tokens"].items() if m in PRICE) / max(len(report), 1)
        _srv = _cost_obj * _objs * _runs
        _gpu_h = _tok_obj * _objs * _runs / 307 / 3600
        _ded = max(_gpu_h, 1) * 4.50
        cc1, cc2 = st.columns(2)
        cc1.metric("Serverless, per month", f"${_srv:,.2f}")
        cc2.metric("Dedicated H100, per month", f"${_ded:,.2f}", f"{_gpu_h:,.1f} GPU-hours of work", delta_color="off")
        st.markdown(f"Migrating **{_objs:,} objects** with **{_runs} full runs a month** costs about **${_srv:,.2f}** on serverless, "
                    f"or about **${_ded:,.2f}** on a dedicated H100 if it is switched on only while working. "
                    + ("Serverless is cheaper at this volume." if _srv <= _ded else "Dedicated is cheaper at this volume."))
        st.caption(f"Based on this run's measured tokens ({_tok_obj:,.0f} per object, worst case at output prices), "
                   "307 tokens/s measured on the dedicated H100 and $4.50 per GPU-hour (minimum one hour).")
    with n_tabs[1]:
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
    with n_tabs[2]:
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
        ded_key = os.environ.get("NEBIUS_NANO_MODEL", "")
        ded_on = bool(os.environ.get("NEBIUS_DEDICATED_BASE_URL")) and ded_key.startswith("dedicated/")
        if ded_on:
            st.success(f"Dedicated endpoint connected: `{ded_key}`. Nano calls (here and in "
                       "\"Run live migration on dedicated\") go to the dedicated H100; Super and Ultra stay serverless.")
        if st.button("Run migration on dedicated endpoint", type="primary" if ded_on else "secondary",
                     disabled=not ded_on, key="run_dedicated",
                     help=None if ded_on else "Locked: the endpoint is stopped to save GPU cost."):
            with st.status("Running Nano translation on the dedicated endpoint...", expanded=True) as stat:
                proc = subprocess.Popen([sys.executable, "-m", "lakeshift.bench", "--target", "dedicated",
                                         "--runs", "1"], env=os.environ.copy(), stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
                for line in proc.stdout:
                    st.text(line.rstrip())
                proc.wait()
                stat.update(label="Dedicated run finished" if proc.returncode == 0 else "Dedicated run failed",
                            state="complete" if proc.returncode == 0 else "error")
        if not ded_on:
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

if section == SECTIONS[3]:
    st.subheader("\U0001f6e1\ufe0f Security")
    st.markdown("""<div class="ls-card"><h4>The hackathon demo setup</h4><ul>
<li>The Oracle database behind this hosted page was opened to the internet <b>only for this hackathon demo</b>.</li>
<li>It runs on a separate Google Cloud VM that holds <b>only synthetic sample data</b>: no real or customer data, and it is not production.</li>
<li>It uses a <b>non-admin demo user with limited grants</b>.</li>
<li>Port 1521 is open but <b>password-protected</b>.</li>
<li>Live runs need a <b>judge access code</b> (shared privately on Devpost) and are <b>capped per day</b> to protect credits and the demo tables.</li>
<li>Every run works in a <b>temporary copy</b>, so the committed results are never overwritten.</li>
<li>Text values are <b>masked before reaching the models</b>: <span class="ls-pass">0 raw customer values sent</span>.</li>
<li>Research is restricted to docs.oracle.com and docs.snowflake.com, and every source is logged.</li>
<li>The VM and port will be <b>shut down after judging ends (Dec 15, 2026)</b>.</li>
</ul></div>
<div class="ls-card"><h4>How we would run it in production</h4><ul>
<li>Private network only: <b>no public database port</b>.</li>
<li>Access over a <b>VPN or private link</b>.</li>
<li><b>Secrets in a vault</b>, never in code or config files.</li>
<li><b>Least-privilege service accounts</b> for every component.</li>
<li><b>Audit logs</b> for every run and every query.</li>
<li>Bring the code to the data: a worker next to the database runs the Oracle side locally and returns only the scorecard, so no customer rows leave the site.</li>
</ul></div>""", unsafe_allow_html=True)
    st.divider()
    st.subheader("Where this applies")
    st.markdown("""
Anywhere legacy Oracle logic must move to the cloud, a wrong number is expensive, and the data must stay private:

- **Banking and insurance:** loyalty and wallet balances, account hierarchies, regulatory reports where a wrong number is a compliance issue.
- **Retail and e-commerce:** rewards points, churn and reorder analytics such as order gaps.
- **Telecom:** customer hierarchies and usage rollups.
- **Healthcare and public sector:** data cannot leave on-prem; masking plus local verification keep it there.
- **Manufacturing:** bill-of-materials hierarchies written with `CONNECT BY`.
- **Consultancies and SIs** running Oracle-to-Snowflake programmes: the row-by-row proof report is the sign-off artifact.
""")
    st.divider()
    st.subheader("\u2753 Questions people ask")
    with st.expander("Why is '' (an empty string) NULL in Oracle?"):
        st.write("Oracle treats an empty piece of text as \"no value\" (NULL). Snowflake treats it as real, empty text. "
                 "So a check like \"email is missing\" can give different answers in the two systems. LakeShift keeps Oracle's meaning, and the proof step catches it if a translation gets it wrong.")
    with st.expander("What does row-by-row proof mean?"):
        st.write("We run the old Oracle code and the new Snowflake code on the same data, then compare every result row, "
                 "value by value. If even one row differs, the object is not done, and it goes back for repair.")
    with st.expander("Why start with the small model?"):
        st.write("Most objects are simple, and the small Nano model gets them right quickly and cheaply. "
                 "Only the objects that fail the proof go to the bigger Super and Ultra models, so you pay for big-model thinking only where it is needed.")
    with st.expander("Is customer data sent to the model?"):
        st.write("No. The models see the code and the shape of the data, never real values. Every text value is masked "
                 "(for example <text#a1b2c3 len=9>), and the run log shows 0 raw customer values sent.")

st.markdown('<div class="ls-foot"><b>' + CREDIT + '</b><br><span>Participant: Suhail Ahmed · LakeShift</span></div>', unsafe_allow_html=True)
