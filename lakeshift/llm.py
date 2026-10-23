import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/",
                api_key=os.environ["NEBIUS_API_KEY"])

ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"
NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
SUPER = "nvidia/nemotron-3-super-120b-a12b"
usage = {}

def chat(model, system, user, retries=2):
    for attempt in range(retries + 1):
        r = client.chat.completions.create(
            model=model, temperature=0, max_tokens=4096,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}])
        usage[model] = usage.get(model, 0) + r.usage.total_tokens
        text = r.choices[0].message.content
        if text and text.strip():
            return text
        print(f"    empty reply from {model.split('/')[-1]} "
              f"(finish_reason={r.choices[0].finish_reason}), retrying...")
    return ""   