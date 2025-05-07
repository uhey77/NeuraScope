import os
from dotenv import load_dotenv
from openai import OpenAI

# .envファイルから環境変数を読み込む
load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
# print(f"--- [translate_util.py] Loaded OPENAI_API_KEY (initial): {OPENAI_API_KEY} ---") # デバッグ用

client = None
if OPENAI_API_KEY and "sk-YOUR_API_KEY_HERE" not in OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-"):
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        # print("--- [translate_util.py] OpenAI client initialized successfully. ---")
    except Exception as e:
        print(f"--- [translate_util.py] Failed to initialize OpenAI client: {e} ---")
else:
    if not OPENAI_API_KEY:
        print("--- [translate_util.py] OpenAI API key is not found in environment variables. ---")
    elif "sk-YOUR_API_KEY_HERE" in OPENAI_API_KEY:
        print("--- [translate_util.py] OpenAI API key is a placeholder. Please set a valid key. ---")
    elif not OPENAI_API_KEY.startswith("sk-"):
         print(f"--- [translate_util.py] OpenAI API key format seems incorrect: {OPENAI_API_KEY[:10]}... ---")


def translate_text_openai(text, target_language="Japanese", model="gpt-3.5-turbo"):
    """OpenAI APIを使ってテキストを翻訳する"""
    if not client:
        return "[Translation service not available: API client not initialized or API key issue]"
    if not text:
        return ""

    try:
        prompt = f"Translate the following English text to {target_language}. Output only the translated text, without any introductory phrases or explanations. If the input is a technical paper title or abstract, maintain the technical accuracy and a natural tone for that context.\n\nEnglish Text:\n\"\"\"\n{text}\n\"\"\"\n\n{target_language} Translation:\n"
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that translates technical text accurately into Japanese."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=int(len(text) * 2.5 + 50)
        )
        translated_text = response.choices[0].message.content.strip()
        return translated_text
    except Exception as e:
        print(f"Error during OpenAI translation: {e}")
        return f"[Translation Error: {str(e)[:100]}]"

def ask_openai_about_paper(paper_title, paper_abstract, user_question, model="gpt-3.5-turbo"):
    """
    OpenAI APIを使って論文に関するユーザーの質問に答える。
    """
    if not client:
        return "[AI Q&A service not available: API client not initialized or API key issue]"
    if not user_question:
        return "質問が空です。"
    if not paper_title or not paper_abstract:
        return "論文情報（タイトルまたはアブストラクト）が不足しています。"

    prompt = f"""
あなたは、科学論文の内容を理解し、それに関する質問に答える専門のアシスタントです。
以下の論文情報とユーザーの質問に基づいて、簡潔かつ正確に回答してください。
回答はユーザーの質問に直接答える形にし、必要に応じて論文の情報を引用または参照してください。
論文に記載のない情報や、あなたの知識のみに基づく推測は避けてください。

論文タイトル: {paper_title}

論文アブストラクト:
{paper_abstract}

ユーザーの質問: {user_question}

回答:
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "あなたはAI論文アシスタントです。与えられた論文のタイトルとアブストラクトに基づいて、ユーザーの質問に答えます。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # 少し事実に基づいて、かつ自然な回答を促す
            max_tokens=700    # 回答の最大長。必要に応じて調整
        )
        answer = response.choices[0].message.content.strip()
        return answer
    except Exception as e:
        error_message = str(e)
        print(f"Error during OpenAI question answering for paper '{paper_title}': {error_message}")
        # APIキー関連のエラーか、他のエラーか判別を試みる
        if "authentication" in error_message.lower() or "api key" in error_message.lower():
            return "[AI Q&A Error: APIキーに問題があるか、認証に失敗しました。]"
        return f"[AI Q&A Error: 回答生成中にエラーが発生しました。詳細はサーバーログを確認してください。 ({error_message[:50]}...)]"


if __name__ == '__main__':
    print(f"--- translate_util.py self-test ---")
    print(f"Loaded OPENAI_API_KEY: {OPENAI_API_KEY}")
    if not client:
        print("OpenAI client not initialized. Cannot run full tests.")
    else:
        print("OpenAI client seems initialized.")
        # 翻訳テスト
        sample_title_en = "Attention Is All You Need"
        print(f"\nTesting translation for: '{sample_title_en}'")
        translated_title = translate_text_openai(sample_title_en)
        print(f"Translated Title: {translated_title}")

        # AI質問テスト
        sample_abstract_en = "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train."
        sample_question = "What is the main contribution of this paper?"
        print(f"\nTesting Q&A for paper '{sample_title_en}' with question: '{sample_question}'")
        qa_answer = ask_openai_about_paper(sample_title_en, sample_abstract_en, sample_question)
        print(f"Q&A Answer: {qa_answer}")

        sample_question_2 = "Does this paper use RNNs?"
        print(f"\nTesting Q&A with question: '{sample_question_2}'")
        qa_answer_2 = ask_openai_about_paper(sample_title_en, sample_abstract_en, sample_question_2)
        print(f"Q&A Answer 2: {qa_answer_2}")
