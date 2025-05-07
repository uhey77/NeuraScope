# app.py
from flask import Flask, render_template, request
from paper.arxiv_fetcher import fetch_arxiv_papers

app = Flask(__name__)

# 利用可能なカテゴリのリスト (ユーザーが選択できるようにするため)
ARXIV_CATEGORIES = [
    "cs.AI", "cs.LG", "cs.CV", "cs.CL", "cs.RO", "stat.ML"
]

@app.route('/', methods=['GET'])
def index():
    selected_category = request.args.get('category', ARXIV_CATEGORIES[0]) # デフォルトは最初のカテゴリ
    if selected_category not in ARXIV_CATEGORIES:
        selected_category = ARXIV_CATEGORIES[0] # 不正な場合はデフォルト

    try:
        papers = fetch_arxiv_papers(category=selected_category, max_results=20)
    except Exception as e:
        print(f"Error fetching papers: {e}")
        papers = [] # エラー時は空のリスト
        error_message = "論文の取得中にエラーが発生しました。時間をおいて再度お試しください。"
        return render_template('index.html', papers=papers, categories=ARXIV_CATEGORIES, selected_category=selected_category, error_message=error_message)

    return render_template('index.html', papers=papers, categories=ARXIV_CATEGORIES, selected_category=selected_category)

if __name__ == '__main__':
    app.run(debug=True) # debug=True は開発中のみ
