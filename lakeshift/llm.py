import json, os
from dotenv import load_dotenv
from openai import OpenAI, APIStatusError, APITimeoutError, APIConnectionError

load_dotenv()
SERVERLESS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

# Cap each call so one slow reply cannot stall a run (the library default is 10 minutes).
TIMEOUT = float(os.getenv("NEBIUS_TIMEOUT", "150"))
client = OpenAI(base_url=SERVERLESS_BASE_URL, api_key=os.environ["NEBIUS_API_KEY"],
                timeout=TIMEOUT, max_retries=1)

ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"
NANO = os.getenv("NEBIUS_NANO_MODEL") or DEFAULT_NANO   # dedicated endpoint: its routing key
SUPER = "nvidia/nemotron-3-super-120b-a12b"

# Optional dedicated endpoint for Nano; Super and Ultra stay on serverless.
_dedicated = os.getenv("NEBIUS_DEDICATED_BASE_URL")
nano_client = (OpenAI(base_url=_dedicated, api_key=os.environ["NEBIUS_API_KEY"],
                      timeout=TIMEOUT, max_retries=1)
               if _dedicated else client)

usage = {}      # model -> total tokens (kept for older code and usage.json "tokens")
details = {}    # model -> calls, prompt, cached, completion, reasoning tokens

# Reasoning effort per model: think less on easy first drafts, more on hard repairs.
# Accepted values: none, minimal, low, medium, high, xhigh. Set to "" to not send it.
EFFORT = {NANO: os.getenv("NEBIUS_EFFORT_NANO", "low"),
          SUPER: os.getenv("NEBIUS_EFFORT_SUPER", "medium"),
          ULTRA: os.getenv("NEBIUS_EFFORT_ULTRA", "high")}

# Structured output: the model must reply as JSON {"sql": ..., "notes": ...}.
# Off by default: a full run scored lower with it on. NEBIUS_STRUCTURED=1 turns it on.
STRUCTURED = os.getenv("NEBIUS_STRUCTURED", "0") == "1"
SQL_SCHEMA = {"type": "json_schema", "json_schema": {
    "name": "sql_answer", "strict": True,
    "schema": {"type": "object",
               "properties": {"sql": {"type": "string"}, "notes": {"type": "string"}},
               "required": ["sql", "notes"], "additionalProperties": False}}}
JSON_HINT = ('\nReply as JSON with two keys: "sql" (the complete SQL statement, '
             'nothing else) and "notes" (one short sentence).')
_unsupported = set()    # (model, option) pairs the endpoint rejected; not sent again

def _record(model, u):
    usage[model] = usage.get(model, 0) + u.total_tokens
    d = details.setdefault(model, {"calls": 0, "prompt": 0, "cached": 0,
                                   "completion": 0, "reasoning": 0})
    p, c = getattr(u, "prompt_tokens_details", None), getattr(u, "completion_tokens_details", None)
    d["calls"] += 1
    d["prompt"] += u.prompt_tokens or 0
    d["completion"] += u.completion_tokens or 0
    d["cached"] += (getattr(p, "cached_tokens", 0) or 0) if p else 0
    d["reasoning"] += (getattr(c, "reasoning_tokens", 0) or 0) if c else 0

def chat(model, system, user, retries=2, structured=False):
    """One chat call. The static system prompt goes first so repeated calls share a
    cached prefix; the per-object text goes last."""
    api = nano_client if model == NANO else client
    for attempt in range(retries + 1):
        kw = {}
        if EFFORT.get(model) and (model, "effort") not in _unsupported:
            kw["reasoning_effort"] = EFFORT[model]
        if structured and (model, "json") not in _unsupported:
            kw["response_format"] = SQL_SCHEMA
        try:
            r = api.chat.completions.create(
                model=model, temperature=0, max_tokens=12000,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}], **kw)
        except APIStatusError as e:
            if e.status_code in (400, 422) and kw:    # option not supported here: drop it
                bad = ("effort" if "reasoning_effort" in kw and "reasoning_effort" in str(e)
                       else "json" if "response_format" in kw else "effort")
                _unsupported.add((model, bad))
                print(f"    {model.split('/')[-1]} rejected {bad} option, continuing without it")
                continue
            raise
        except (APITimeoutError, APIConnectionError):
            # A slow or dropped reply should not crash the run: try again, then give up
            # on this call only (the caller treats "" as a draft to repair).
            print(f"    {model.split('/')[-1]} timed out (attempt {attempt + 1}), "
                  + ("retrying..." if attempt < retries else "moving on"))
            continue
        _record(model, r.usage)
        text = r.choices[0].message.content    # reasoning comes back separately (reasoning_content)
        if text and text.strip():
            return text
        print(f"    empty reply from {model.split('/')[-1]} "
              f"(finish_reason={r.choices[0].finish_reason}), retrying...")
    return ""

def chat_sql(model, system, user):
    """Ask for SQL. With structured output the SQL is read from the JSON reply; if that
    is off, unsupported or the JSON is broken, the raw text is returned for the caller's
    text cleaner."""
    if not STRUCTURED or (model, "json") in _unsupported:
        return chat(model, system, user)
    text = chat(model, system + JSON_HINT, user, structured=True)
    try:
        sql = json.loads(text).get("sql", "")
        if isinstance(sql, str) and sql.strip():
            return sql.strip()
    except (ValueError, AttributeError):
        pass
    return text

def usage_report():
    """Per-model usage for migrated/usage.json, keyed by short model name."""
    return {k.split("/")[-1]: dict(v) for k, v in details.items()}
