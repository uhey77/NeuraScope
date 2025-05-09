from __future__ import annotations
import os, backoff, openai

openai.api_key = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

SYSTEM = (
    "あなたは学術論文を詳細に解析して報告する日本語アシスタントです。"
    "読み手は大学院レベルの技術者です。"
)

PROMPT = """
タイトルと要約から、以下の 8 項目を Markdown で 150〜250 字ずつまとめてください。
### 1. タイトル
### 2. 研究の背景
### 3. 目的
### 4. 方法
### 5. 主な結果
### 6. 意義
### 7. 今後の展望
### 8. 140字ツイート
8. はハッシュタグ付き 140 字以内で。
"""

@backoff.on_exception(backoff.expo, openai.OpenAIError, max_tries=5, jitter=None)
def _chat(msgs):  # type: ignore[valid-type]
    return openai.chat.completions.create(
        model=MODEL, messages=msgs, temperature=0.3
    ).choices[0].message.content.strip()

def generate_analysis(title: str, abstract: str) -> tuple[str, str]:
    md = _chat([
        {"role":"system","content":SYSTEM},
        {"role":"system","content":PROMPT},
        {"role":"user","content":f"タイトル: {title}\n\n要約: {abstract}"}
    ])
    tweet = md.splitlines()[-1].strip()
    if len(tweet) > 140: tweet = tweet[:137] + "…"
    return md, tweet
