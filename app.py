from __future__ import annotations
import os, sqlite3, arxiv, markdown, feedparser, requests, backoff
from contextlib import closing
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify, redirect, url_for

from feeds import FEEDS
from translate_util import translate_text_openai
from analysis_util  import generate_analysis

DB_PATH = "neurascope.db"
UA      = {"User-Agent": "Mozilla/5.0 (NeuraScope)"}

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# ───────────────────────── DB
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with closing(get_db()) as conn, open("schema.sql", encoding="utf-8") as f:
        conn.executescript(f.read())
        conn.commit()

# ───────────────────────── arXiv 取得
def fetch_arxiv():
    print("[arxiv] start")
    with closing(get_db()) as conn:
        cur = conn.cursor()
        search = arxiv.Search(
            "cat:cs.AI OR cat:cs.LG",
            sort_by=arxiv.SortCriterion.SubmittedDate,
            max_results=20,
        )
        for r in search.results():                                     # type:ignore[attr-defined]
            aid = r.get_short_id()
            if cur.execute("SELECT 1 FROM papers WHERE arxiv_id=?", (aid,)).fetchone():
                continue
            title_en = r.title.strip()
            abstract_en = r.summary.strip()
            title_ja = translate_text_openai(title_en)
            abstract_ja = translate_text_openai(abstract_en)
            analysis_ja, tweet_ja = generate_analysis(title_ja, abstract_ja)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            cur.execute(
                """INSERT INTO papers
                  (arxiv_id,title_en,title_ja,abstract_en,abstract_ja,
                   authors,categories,comment,published_at,
                   analysis_ja,tweet_ja,pdf_url,
                   favorite,created_at,translated_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    aid,
                    title_en,
                    title_ja,
                    abstract_en,
                    abstract_ja,
                    ", ".join(a.name for a in r.authors),
                    " ".join(r.categories),
                    (r.comment or "").strip(),
                    r.published.isoformat(timespec="seconds"),
                    analysis_ja,
                    tweet_ja,
                    next((l.href for l in r.links if l.title == "pdf"), None),
                    0,
                    now,
                    now,
                ),
            )
        conn.commit()
    print("[arxiv] end")

# ───────────────────────── 外部フィード取得
def fetch_feeds():
    print("[feeds] start")
    with closing(get_db()) as conn:
        cur = conn.cursor()
        for sid, meta in FEEDS.items():
            print("  ─", meta["name"])
            try:
                entries = _get_entries(meta)
            except Exception as e:
                print("    ⚠️ skip:", e)
                continue
            added = 0
            for e in entries:
                title_en = e["title"].strip()
                link = e["link"].split("?")[0]
                if not title_en or not link:
                    continue
                if cur.execute("SELECT 1 FROM articles WHERE link=?", (link,)).fetchone():
                    continue
                summary_en = e.get("summary", "").strip()
                pub = e.get("published", "")[:25]
                title_ja = translate_text_openai(title_en)
                summary_ja = translate_text_openai(summary_en) if summary_en else None
                cur.execute(
                    """INSERT INTO articles
                      (title_en,title_ja,link,summary_en,summary_ja,
                       published,source_id,category,favorite)
                      VALUES (?,?,?,?,?,?,?,? ,0)""",
                    (
                        title_en,
                        title_ja,
                        link,
                        summary_en,
                        summary_ja,
                        pub,
                        sid,
                        meta["category"],
                    ),
                )
                added += 1
            print(f"    +{added}")
        conn.commit()
    print("[feeds] end")

def _get_entries(meta: dict):
    kind = meta.get("scrape")
    if kind == "gh":
        return _scrape_github()
    if kind == "hf":
        return _scrape_hf()
    if kind == "pwc":
        return _scrape_pwc()
    if kind == "batch":
        return _scrape_batch()
    r = requests.get(meta["url"], headers=UA, timeout=20)
    r.raise_for_status()
    return feedparser.parse(r.content).entries

def _scrape_github():
    htmltxt = requests.get("https://github.com/trending?since=daily", headers=UA, timeout=20).text
    soup = BeautifulSoup(htmltxt, "html.parser")
    results = []
    for row in soup.select("article.Box-row"):
        a_tag = row.select_one("h3 > a, h2 > a")
        if not a_tag:
            continue
        desc_tag = row.select_one("p")
        results.append(
            {
                "title": a_tag.get_text(" ", strip=True),
                "link": "https://github.com" + a_tag["href"],
                "summary": desc_tag.get_text(strip=True) if desc_tag else "",
            }
        )
    return results

def _scrape_hf():
    htmltxt = requests.get("https://huggingface.co/papers", headers=UA, timeout=20).text
    soup = BeautifulSoup(htmltxt, "html.parser")
    for li in soup.select("li.paper-item"):
        h = li.select_one("h4") or li.select_one("h3")
        a = li.select_one("a[href*='/papers/']")
        if not h or not a:
            continue
        p = li.select_one("p")
        yield {
            "title": h.get_text(strip=True),
            "link": "https://huggingface.co" + a["href"],
            "summary": p.get_text(strip=True) if p else "",
        }

def _scrape_pwc():
    htmltxt = requests.get("https://paperswithcode.com/trending", headers=UA, timeout=20).text
    soup = BeautifulSoup(htmltxt, "html.parser")
    for card in soup.select("div.paper-card"):
        h = card.select_one("h1 a")
        abs_p = card.select_one("p[itemprop='description']")
        if not h:
            continue
        yield {
            "title": h.get_text(strip=True),
            "link": "https://paperswithcode.com" + h["href"],
            "summary": abs_p.get_text(strip=True) if abs_p else "",
        }

def _scrape_batch():
    htmltxt = requests.get("https://www.deeplearning.ai/the-batch/", headers=UA, timeout=20).text
    soup = BeautifulSoup(htmltxt, "html.parser")
    for art in soup.select("article.post-preview, div.post-block"):
        h = art.select_one("h3") or art.select_one("h2")
        a = art.select_one("a[href]")
        if not h or not a:
            continue
        p = art.select_one("div.excerpt") or art.select_one("p")
        yield {
            "title": h.get_text(strip=True),
            "link": a["href"],
            "summary": p.get_text(strip=True) if p else "",
        }

# ───────────────────────── UI Helpers
MD_EXT = ["fenced_code", "tables", "toc"]

def group_arxiv(fav: bool = False):
    where = "WHERE favorite=1" if fav else ""
    with closing(get_db()) as conn:
        rows = conn.execute(
            f"""
          SELECT id,title_ja,favorite,analysis_ja,pdf_url,
                 substr(created_at,1,10) AS cdate
            FROM papers {where}
        ORDER BY created_at DESC"""
        ).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["cdate"], []).append(
            {
                **dict(r),
                "analysis_html": markdown.markdown(r["analysis_ja"] or "", extensions=MD_EXT),
            }
        )
    return sorted(out.items(), reverse=True)

def ext_by_cat(fav: bool = False, days: int = 90, limit: int = 60):
    where = "WHERE favorite=1" if fav else ""
    with closing(get_db()) as conn:
        rows = conn.execute(
            f"""
            SELECT *,substr(created_at,1,10) AS cdate FROM articles {where}
        ORDER BY created_at DESC"""
        ).fetchall()
    cats = {"paper": {}, "news": {}, "blog": {}}
    for r in rows:
        g = cats[r["category"]].setdefault(r["cdate"], [])
        if len(g) < limit:
            g.append(r)
    for cat in cats:
        cats[cat] = dict(list(cats[cat].items())[: days])
    return cats

# ───────────────────────── Routes
def _render_index(fav: bool = False):
    arxiv = group_arxiv(fav)
    return render_template(
        "index.html",
        arxiv_days=dict(arxiv),
        ordered_dates=[d for d, _ in arxiv],
        ext_by_cat=ext_by_cat(fav),
        fav_only=fav,
    )

@app.route("/")
def index():
    return _render_index(False)

@app.route("/favorites")
def favorites():
    # お気に入り表示用のページをレンダリング
    return _render_index(True)

@app.route("/article/<int:article_id>")
def article_detail(article_id: int):
    """外部フィード記事の詳細ページ"""
    # article_idがどのテーブルに属するか確認
    article_type = "article"  # articleか paperか
    
    with closing(get_db()) as conn:
        # まずparticlesテーブルを探す
        a = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        if not a:
            # なければpapersテーブルを探す
            a = conn.execute("SELECT * FROM papers WHERE id=?", (article_id,)).fetchone()
            if not a:
                return redirect(url_for("index"))
            article_type = "paper"  # これはarXiv論文
        
        # article_qa テーブルが存在しない場合は作成
        try:
            conn.execute("SELECT 1 FROM article_qa LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS article_qa (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                    question    TEXT NOT NULL,
                    answer_md   TEXT NOT NULL,
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        
        # Q&Aデータを取得
        qa_list = []
        if article_type == "article":
            # articlesの場合はarticle_qaテーブルから取得
            qa = conn.execute(
                "SELECT * FROM article_qa WHERE article_id=? ORDER BY created_at DESC", (article_id,)
            ).fetchall()
            
            if qa:
                qa_list = [
                    {
                        "question": q["question"],
                        "answer_html": markdown.markdown(q["answer_md"], extensions=MD_EXT),
                        "created_at": q["created_at"][:10],
                    }
                    for q in qa
                ]
        else:
            # papersの場合はqaテーブルから取得
            qa = conn.execute(
                "SELECT * FROM qa WHERE paper_id=? ORDER BY created_at DESC", (article_id,)
            ).fetchall()
            
            if qa:
                qa_list = [
                    {
                        "question": q["question"],
                        "answer_html": markdown.markdown(q["answer_md"], extensions=MD_EXT),
                        "created_at": q["created_at"][:10],
                    }
                    for q in qa
                ]
    
    # aを辞書に変換
    article_dict = dict(a)
    
    # カテゴリラベルを設定
    if article_type == "paper":
        category_label = "arXiv"
        # papers用のテンプレートに修正するための追加情報
        article_dict["is_arxiv"] = True
    else:
        category_map = {
            'paper': '論文フィード',
            'news': 'ニュース',
            'blog': '技術ブログ'
        }
        category_label = category_map.get(article_dict.get("category", ""), "")
        article_dict["is_arxiv"] = False
    
    # 質問用APIのエンドポイントを設定
    api_endpoint = "api/ask-article" if article_type == "article" else "api/ask"
    article_dict["api_endpoint"] = api_endpoint
    
    return render_template(
        "article.html", 
        article=article_dict, 
        qa_list=qa_list,
        category_label=category_label,
        article_type=article_type
    )

@app.route("/paper/<int:paper_id>")
def paper_detail(paper_id: int):
    """arXiv論文の詳細ページ"""
    with closing(get_db()) as conn:
        p = conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
        if not p:
            return redirect(url_for("index"))
        qa = conn.execute(
            "SELECT * FROM qa WHERE paper_id=? ORDER BY created_at DESC", (paper_id,)
        ).fetchall()
    analysis_html = markdown.markdown(p["analysis_ja"] or "", extensions=MD_EXT)
    qa_list = [
        {
            "question": q["question"],
            "answer_html": markdown.markdown(q["answer_md"], extensions=MD_EXT),
            "created_at": q["created_at"][:10],
        }
        for q in qa
    ]
    return render_template("paper.html", paper=p, analysis_html=analysis_html, qa_list=qa_list)

@app.route("/api/favorite/<tbl>/<int:rid>", methods=["POST"])
def api_fav(tbl: str, rid: int):
    fav = 1 if request.json.get("favorite") else 0
    table = "papers" if tbl == "paper" else "articles"
    with closing(get_db()) as conn:
        conn.execute(f"UPDATE {table} SET favorite=? WHERE id=?", (fav, rid))
        conn.commit()
    return jsonify(ok=True, favorite=bool(fav))

# ───────────────────────── Q&A API
@app.route("/api/ask", methods=["POST"])
def api_ask():
    """
    JSON 形式:
      {
        "paper_id": 123,
        "question": "〜〜とは何ですか？"
      }
    返り値:
      {
        "answer_html": "<p>回答 (Markdown → HTML)</p>",
        "question": "質問",
        "created_at": "YYYY-MM-DD"
      }
    """
    data = request.json or {}
    try:
        pid = int(data["paper_id"])
        question = data["question"].strip()
    except Exception:
        return jsonify(error="invalid payload"), 400
    if not question:
        return jsonify(error="empty question"), 400

    with closing(get_db()) as conn:
        p = conn.execute("SELECT * FROM papers WHERE id=?", (pid,)).fetchone()
    if not p:
        return jsonify(error="paper not found"), 404

    import openai

    @backoff.on_exception(backoff.expo, openai.OpenAIError, max_tries=3)
    def _chat_completion(msgs):
        return (
            openai.chat.completions.create(
                model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
                messages=msgs,
                temperature=0.3,
            )
            .choices[0]
            .message.content.strip()
        )

    system_prompt = "あなたは論文解説アシスタントです。回答は日本語で Markdown 形式で返してください。"
    user_prompt = f"""論文タイトル:
{p["title_ja"]}

要約:
{p["analysis_ja"]}

質問:
{question}
"""
    answer_md = _chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )

    with closing(get_db()) as conn:
        conn.execute(
            "INSERT INTO qa (paper_id, question, answer_md) VALUES (?,?,?)",
            (pid, question, answer_md),
        )
        conn.commit()

    answer_html = markdown.markdown(answer_md, extensions=MD_EXT)
    return jsonify(
        answer_html=answer_html,
        question=question,
        created_at=datetime.now().strftime("%Y-%m-%d"),
    )

@app.route("/api/ask-article", methods=["POST"])
def api_ask_article():
    """
    外部フィード記事にAIが回答するAPI
    JSON 形式:
      {
        "article_id": 123,
        "question": "この記事について教えてください"
      }
    返り値:
      {
        "answer_html": "<p>回答 (Markdown → HTML)</p>",
        "question": "質問",
        "created_at": "YYYY-MM-DD"
      }
    """
    data = request.json or {}
    try:
        article_id = int(data["article_id"])
        question = data["question"].strip()
    except Exception:
        return jsonify(error="invalid payload"), 400
    if not question:
        return jsonify(error="empty question"), 400

    with closing(get_db()) as conn:
        a = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    if not a:
        return jsonify(error="article not found"), 404

    import openai

    @backoff.on_exception(backoff.expo, openai.OpenAIError, max_tries=3)
    def _chat_completion(msgs):
        return (
            openai.chat.completions.create(
                model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
                messages=msgs,
                temperature=0.3,
            )
            .choices[0]
            .message.content.strip()
        )

    system_prompt = """あなたは記事解説アシスタントです。
与えられたタイトルと要約に基づいて、質問に日本語で回答してください。
回答は Markdown 形式で返してください。"""
    
    user_prompt = f"""タイトル:
{a["title_ja"] or a["title_en"]}

要約:
{a["summary_ja"] or a["summary_en"] or "要約なし"}

出典: {a["source_id"]}
リンク: {a["link"]}

質問:
{question}
"""
    answer_md = _chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )

    # 回答をデータベースに保存
    with closing(get_db()) as conn:
        # article_qa テーブルが存在しない場合は作成
        conn.execute("""
            CREATE TABLE IF NOT EXISTS article_qa (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                question    TEXT NOT NULL,
                answer_md   TEXT NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "INSERT INTO article_qa (article_id, question, answer_md) VALUES (?,?,?)",
            (article_id, question, answer_md),
        )
        conn.commit()

    answer_html = markdown.markdown(answer_md, extensions=MD_EXT)
    return jsonify(
        answer_html=answer_html,
        question=question,
        created_at=datetime.now().strftime("%Y-%m-%d"),
    )

# ───────────────────────── CLI 起動
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-arxiv", action="store_true")
    parser.add_argument("--fetch-feeds", action="store_true")
    args = parser.parse_args()

    if args.fetch_arxiv:
        fetch_arxiv()
    elif args.fetch_feeds:
        fetch_feeds()
    else:
        if not os.path.exists(DB_PATH):
            init_db()
        app.run(debug=True, host="0.0.0.0", port=8000)
