import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ["NEBIUS_API_KEY"],
)

resp = client.chat.completions.create(
    model="nvidia/Nemotron-3_5-Lightning",
    messages=[{"role": "user", "content": "Explain Oracle NVL in one sentence."}],
)
print(resp.choices[0].message.content)
print("tokens used:", resp.usage.total_tokens)