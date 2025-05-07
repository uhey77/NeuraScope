import os
import sqlite3
from datetime import datetime as dt_core
from flask import Flask, render_template, request, g, jsonify, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
import pytz


from paper.arxiv_fetcher import fetch_arxiv_papers, ArxivFetchError
# translate_utilから必要な関数をインポート
from translate_util import translate_text_openai, ask_openai_about_paper

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATABASE = 'navigator.db'
ARXIV_CATEGORIES = ["cs.AI", "cs.LG", "cs.CV", "cs.CL", "cs.RO", "stat.ML", "cs.NE"]
PAPERS_PER_PAGE = 20

# --- Database Helpers ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db_command():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
    print('Initialized the database.')

@app.cli.command('init-db')
def init_db_cli_command():
    init_db_command()

# --- Background Scheduler ---
scheduler = BackgroundScheduler(daemon=True, timezone=str(pytz.timezone('Asia/Tokyo')))

def store_papers_to_db(category, papers_list):
    if not papers_list: return
    with app.app_context():
        db = get_db()
        for paper in papers_list:
            try:
                dt_str_part = " ".join(paper['published_date'].split(' ')[:2])
                dt_obj = dt_core.strptime(dt_str_part, '%Y-%m-%d %H:%M:%S')
                published_ts = int(dt_obj.timestamp())
            except ValueError as e:
                print(f"ValueError parsing date {paper['published_date']} for {paper['arxiv_id']}: {e}")
                published_ts = int(dt_core.now().timestamp())
            try:
                db.execute("""
                    INSERT INTO articles (arxiv_id, title, authors, published_date_str, published_ts, summary, link_arxiv, link_pdf, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(arxiv_id) DO UPDATE SET
                        title=excluded.title, authors=excluded.authors, published_date_str=excluded.published_date_str,
                        published_ts=excluded.published_ts, summary=excluded.summary, link_arxiv=excluded.link_arxiv,
                        link_pdf=excluded.link_pdf, category=excluded.category, fetched_at=CURRENT_TIMESTAMP
                """, (
                    paper['arxiv_id'], paper['title'], paper['authors'], paper['published_date'],
                    published_ts, paper['summary'], paper['link_arxiv'], paper['link_pdf'], category
                ))
            except sqlite3.Error as e:
                print(f"DB Error inserting/updating paper {paper['arxiv_id']} for {category}: {e}")
        db.commit()

def scheduled_fetch_job(category_to_fetch):
    print(f"[{dt_core.now()}] SCHED: Fetching papers for category: {category_to_fetch}...")
    try:
        papers = fetch_arxiv_papers(category=category_to_fetch, max_results=50)
        if papers:
            store_papers_to_db(category_to_fetch, papers)
            print(f"[{dt_core.now()}] SCHED: Stored {len(papers)} papers for {category_to_fetch}.")
        else:
            print(f"[{dt_core.now()}] SCHED: No new papers or error for {category_to_fetch}.")
    except ArxivFetchError as e:
        print(f"[{dt_core.now()}] SCHED: ArxivFetchError for {category_to_fetch}: {e}")
    except Exception as e:
        print(f"[{dt_core.now()}] SCHED: Unexpected error for {category_to_fetch}: {e}")

# --- Favorite Functions ---
def add_favorite(arxiv_id, title, link_arxiv):
    db = get_db()
    try:
        db.execute('INSERT INTO favorites (arxiv_id, title, link_arxiv) VALUES (?, ?, ?)', (arxiv_id, title, link_arxiv))
        db.commit(); return True
    except sqlite3.IntegrityError: return False
    except sqlite3.Error as e: print(f"DB error adding favorite {arxiv_id}: {e}"); db.rollback(); return False

def remove_favorite(arxiv_id):
    db = get_db()
    try:
        db.execute('DELETE FROM favorites WHERE arxiv_id = ?', (arxiv_id,)); db.commit(); return True
    except sqlite3.Error as e: print(f"DB error removing favorite {arxiv_id}: {e}"); db.rollback(); return False

def is_favorite(arxiv_id):
    if not arxiv_id: return False
    db = get_db(); cur = db.execute('SELECT 1 FROM favorites WHERE arxiv_id = ?', (arxiv_id,)); return cur.fetchone() is not None

def get_all_favorites_from_db():
    db = get_db()
    cur = db.execute('SELECT arxiv_id, title, link_arxiv, added_at FROM favorites ORDER BY added_at DESC')
    favorites_list = []
    for row in cur.fetchall():
        fav_dict = dict(row)
        if fav_dict['added_at']:
            try: fav_dict['added_at'] = dt_core.strptime(fav_dict['added_at'], '%Y-%m-%d %H:%M:%S')
            except ValueError: fav_dict['added_at'] = None
        favorites_list.append(fav_dict)
    return favorites_list

# --- Translation DB Update ---
def update_translation_in_db(arxiv_id, translated_title, translated_summary):
    db = get_db()
    try:
        db.execute("""
            UPDATE articles SET translated_title_ja = ?, translated_summary_ja = ? WHERE arxiv_id = ?
        """, (translated_title, translated_summary, arxiv_id)); db.commit(); return True
    except sqlite3.Error as e: print(f"DB Error updating translation for {arxiv_id}: {e}"); db.rollback(); return False

# --- Routes ---
@app.route('/', methods=['GET'])
def index():
    selected_category = request.args.get('category', ARXIV_CATEGORIES[0])
    if selected_category not in ARXIV_CATEGORIES: selected_category = ARXIV_CATEGORIES[0]
    page = request.args.get('page', 1, type=int); offset = (page - 1) * PAPERS_PER_PAGE
    papers_data = []; error_message = None; total_papers = 0
    try:
        db = get_db()
        count_cur = db.execute("SELECT COUNT(*) FROM articles WHERE category = ?", (selected_category,))
        total_papers = count_cur.fetchone()[0]
        cur = db.execute(f"""
            SELECT arxiv_id, title, authors, published_date_str, summary, link_arxiv, link_pdf, category,
                   translated_title_ja, translated_summary_ja
            FROM articles WHERE category = ? ORDER BY published_ts DESC LIMIT ? OFFSET ?
        """, (selected_category, PAPERS_PER_PAGE, offset))
        raw_papers_from_db = cur.fetchall()
        if not raw_papers_from_db and page == 1:
            # print(f"No papers in DB for {selected_category}, attempting live fetch...")
            try:
                live_papers = fetch_arxiv_papers(category=selected_category, max_results=PAPERS_PER_PAGE * 2)
                if live_papers:
                    store_papers_to_db(selected_category, live_papers)
                    cur = db.execute(f"""
                        SELECT arxiv_id, title, authors, published_date_str, summary, link_arxiv, link_pdf, category,
                               translated_title_ja, translated_summary_ja
                        FROM articles
                        WHERE category = ?
                        ORDER BY published_ts DESC
                        LIMIT ? OFFSET ?
                    """, (selected_category, PAPERS_PER_PAGE, offset))
                    raw_papers_from_db = cur.fetchall()
                    count_cur = db.execute("SELECT COUNT(*) FROM articles WHERE category = ?", (selected_category,)); total_papers = count_cur.fetchone()[0]
            except ArxivFetchError as live_e: error_message = f"ライブ取得中にエラー: {live_e}"
        if not raw_papers_from_db: error_message = f"カテゴリ '{selected_category}' で論文が見つかりませんでした。"
        else:
            for paper_row in raw_papers_from_db:
                p_dict = dict(paper_row); p_dict['is_favorite'] = is_favorite(p_dict['arxiv_id']); papers_data.append(p_dict)
    except Exception as e: print(f"Error in index route: {e}"); error_message = "論文の取得中に予期せぬエラーが発生しました。"
    total_pages = (total_papers + PAPERS_PER_PAGE - 1) // PAPERS_PER_PAGE
    return render_template('index.html', papers=papers_data, categories=ARXIV_CATEGORIES,
                           selected_category=selected_category, error_message=error_message,
                           current_page=page, total_pages=total_pages)

@app.route('/favorite/toggle', methods=['POST'])
def favorite_toggle_route():
    data = request.json; arxiv_id = data.get('arxiv_id'); title = data.get('title'); link_arxiv = data.get('link_arxiv')
    if not arxiv_id: return jsonify({'success': False, 'message': 'Missing arxiv_id'}), 400
    if is_favorite(arxiv_id):
        if remove_favorite(arxiv_id): return jsonify({'success': True, 'status': 'removed', 'arxiv_id': arxiv_id})
        else: return jsonify({'success': False, 'message': 'Error removing favorite'}), 500
    else:
        if not title or not link_arxiv: return jsonify({'success': False, 'message': 'Missing title or link_arxiv for new favorite'}), 400
        if add_favorite(arxiv_id, title, link_arxiv): return jsonify({'success': True, 'status': 'added', 'arxiv_id': arxiv_id})
        else: return jsonify({'success': False, 'message': 'Error adding favorite'}), 500

@app.route('/favorites')
def favorites_page():
    favorites_list = get_all_favorites_from_db()
    return render_template('favorites.html', favorites=favorites_list)

@app.route('/translate-article', methods=['POST'])
def translate_article_route():
    data = request.json; arxiv_id = data.get('arxiv_id')
    if not arxiv_id: return jsonify({'success': False, 'message': 'arxiv_id is required'}), 400
    db = get_db(); article_row = db.execute('SELECT title, summary, translated_title_ja, translated_summary_ja FROM articles WHERE arxiv_id = ?', (arxiv_id,)).fetchone()
    if not article_row: return jsonify({'success': False, 'message': 'Article not found in DB'}), 404
    if article_row['translated_title_ja'] and article_row['translated_summary_ja']:
        return jsonify({'success': True, 'status': 'cached', 'arxiv_id': arxiv_id,
                        'translated_title': article_row['translated_title_ja'], 'translated_summary': article_row['translated_summary_ja']})
    original_title = article_row['title']; original_summary = article_row['summary']
    translated_title = translate_text_openai(original_title)
    translated_summary = translate_text_openai(original_summary)
    if any(err_msg in text for text in [translated_title, translated_summary] for err_msg in ["[Translation Error:", "[Translation service not available"]):
         return jsonify({'success': False, 'message': 'Translation failed.', 'translated_title': translated_title, 'translated_summary': translated_summary}), 500
    if update_translation_in_db(arxiv_id, translated_title, translated_summary):
        return jsonify({'success': True, 'status': 'translated', 'arxiv_id': arxiv_id, 'translated_title': translated_title, 'translated_summary': translated_summary})
    else: return jsonify({'success': False, 'message': 'Failed to save translation to DB'}), 500

@app.route('/ask-ai', methods=['POST']) # ★★★ 新しいエンドポイント ★★★
def ask_ai_route():
    data = request.json
    arxiv_id = data.get('arxiv_id')
    user_question = data.get('question')

    if not arxiv_id or not user_question:
        return jsonify({'success': False, 'message': 'arxiv_id と question は必須です。'}), 400

    db = get_db()
    article_row = db.execute(
        'SELECT title, summary FROM articles WHERE arxiv_id = ?', (arxiv_id,)
    ).fetchone()

    if not article_row:
        return jsonify({'success': False, 'message': '指定された論文が見つかりません。'}), 404

    paper_title = article_row['title']
    paper_abstract = article_row['summary']

    if not paper_abstract: # アブストラクトがない場合は、タイトルだけでも試みるかエラーにする
        # return jsonify({'success': False, 'message': 'この論文のアブストラクト情報がありません。'}), 400
        print(f"Warning: Abstract not found for paper {arxiv_id}. Asking question based on title only.")
        # paper_abstract = "アブストラクトはありません。" # または空文字列

    # translate_util.py に定義した ask_openai_about_paper を使用
    ai_answer = ask_openai_about_paper(paper_title, paper_abstract, user_question)

    # エラーメッセージが返ってきたかチェック
    if any(err_msg in ai_answer for err_msg in ["[AI Q&A Error:", "[AI Q&A service not available"]):
        return jsonify({'success': False, 'message': ai_answer}), 500

    return jsonify({'success': True, 'answer': ai_answer})


# --- Initialize DB and Scheduler ---
if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        print(f"{DATABASE} not found. Initializing database via flask init-db or manually.")
        # flask init-db コマンドで初期化することを推奨
        # ここで直接 init_db_command() を呼ぶと、uv run などではコンテキストエラーになることがある
    
    if not scheduler.running:
        for cat in ARXIV_CATEGORIES:
            scheduler.add_job(
                func=scheduled_fetch_job, trigger='interval', args=[cat],
                hours=2, id=f"fetch_job_{cat}", replace_existing=True,
                next_run_time=dt_core.now() # アプリ起動時に一度実行
            )
        try:
            scheduler.start()
            print("APScheduler started successfully.")
            atexit.register(lambda: scheduler.shutdown() if scheduler.running else None)
        except Exception as e: print(f"Failed to start APScheduler: {e}")
    
    # Debug mode on, but use_reloader=False for APScheduler stability with Flask dev server
    # For production, use a proper WSGI server like Gunicorn.
    app.run(debug=True, use_reloader=False)