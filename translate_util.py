import os
from openai import OpenAI
from dotenv import load_dotenv
# from openai import OpenAIError # 必要に応じて

load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = None
if OPENAI_API_KEY and "YOUR_API_KEY" not in OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"Failed to initialize OpenAI client: {e}")
else:
    print("OpenAI API key is not set or is a placeholder. Translation will not work.")


def translate_text_openai(text, target_language="Japanese", model="gpt-3.5-turbo"):
    """OpenAI APIを使ってテキストを翻訳する"""
    if not client:
        return "[Translation service not available: API client not initialized]"
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
            temperature=0.2, # 翻訳なので創造性は低め
            max_tokens=int(len(text) * 2.5 + 50) # 日本語はトークンが多いことと、ある程度の余裕を考慮
        )
        translated_text = response.choices[0].message.content.strip()
        return translated_text
    # except OpenAIError as e:
    #     print(f"OpenAI API Error during translation: {e}")
    #     return f"[Translation API Error: {str(e)[:100]}]" # エラーメッセージを短縮して返す
    except Exception as e:
        print(f"Error during OpenAI translation: {e}")
        return f"[Translation Error: {str(e)[:100]}]"


if __name__ == '__main__':
    if not client:
        print("OpenAI client not initialized. Please set your API key in translate_util.py to run this test.")
    else:
        sample_title = "Attention Is All You Need"
        sample_summary = "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train."
        
        print(f"Original Title: {sample_title}")
        translated_title = translate_text_openai(sample_title)
        print(f"Translated Title: {translated_title}")
        
        print(f"\nOriginal Summary (first 100 chars): {sample_summary[:100]}...")
        translated_summary = translate_text_openai(sample_summary)
        print(f"Translated Summary (first 100 chars): {translated_summary[:100]}...")
