from __future__ import annotations
import os, backoff, openai

openai.api_key = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

@backoff.on_exception(backoff.expo, openai.OpenAIError, max_tries=5, jitter=None)
def _chat(msgs):  # type: ignore[valid-type]
    return openai.chat.completions.create(model=MODEL, messages=msgs, temperature=0.2
    ).choices[0].message.content.strip()

def translate_text_openai(text: str, target_lang: str = "ja") -> str:
    sys = ("You are a professional translator. "
           f"Translate everything into {target_lang}. Return only the translation.")
    try:
        return _chat([{"role":"system","content":sys},{"role":"user","content":text}])
    except Exception as exc:  # noqa: BLE001
        print("[translate_util] failed:", exc); return text
