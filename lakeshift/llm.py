import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
SERVERLESS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

client = OpenAI(base_url=SERVERLESS_BASE_URL, api_key=os.environ["NEBIUS_API_KEY"])

ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"
NANO = os.getenv("NEBIUS_NANO_MODEL") or DEFAULT_NANO   # dedicated endpoint: its routing key
SUPER = "nvidia/nemotron-3-super-120b-a12b"

# Optional dedicated endpoint for Nano; Super and Ultra stay on serverless.
_dedicated = os.getenv("NEBIUS_DEDICATED_BASE_URL")
nano_client = (OpenAI(base_url=_dedicated, api_key=os.environ["NEBIUS_API_KEY"])
               if _dedicated else client)
usage = {}

def chat(model, system, user, retries=2):
    api = nano_client if model == NANO else client
    for attempt in range(retries + 1):
        r = api.chat.completions.create(
            model=model, temperature=0, max_tokens=12000,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}])
        usage[model] = usage.get(model, 0) + r.usage.total_tokens
        text = r.choices[0].message.content
        if text and text.strip():
            return text
        print(f"    empty reply from {model.split('/')[-1]} "
              f"(finish_reason={r.choices[0].finish_reason}), retrying...")
    return ""
