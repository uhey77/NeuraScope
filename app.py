from __future__ import annotations
import os, sqlite3, arxiv, markdown
from contextlib import closing
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, redirect, url_for

from translate_util import translate_text_openai
from analysis_util  import generate_analysis

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH  = os.path.join(BASE_DIR, "neurascope.db")

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# ── DB helpers ---------------------------------------------------------
def get_db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c

def init_db() -> None:
    with closing(get_db()) as conn, open(os.path.join(BASE_DIR,"schema.sql"),encoding="utf-8") as f:
        conn.executescript(f.read()); conn.commit()

# ── Scheduled fetch job -----------------------------------------------
ARXIV_QUERY = "cat:cs.AI OR cat:cs.LG"; MAX = 20
def scheduled_fetch_job() -> None:
    print("[fetch] start")
    with closing(get_db()) as conn:
        cur = conn.cursor()
        for r in arxiv.Search(query=ARXIV_QUERY,
                              sort_by=arxiv.SortCriterion.SubmittedDate,
                              max_results=MAX).results():     # type: ignore[attr-defined]
            aid = r.get_short_id()
            if cur.execute("SELECT 1 FROM papers WHERE arxiv_id=?", (aid,)).fetchone():
                continue
            # meta
            title_en  = r.title.strip()
            abstract_en = r.summary.strip()
            pdf_url   = next((l.href for l in r.links if l.title=="pdf"),None)
            authors   = ", ".join(a.name for a in r.authors)
            categories= " ".join(r.categories)
            comment   = (r.comment or "").strip()
            pub_at    = r.published.isoformat(timespec="seconds")

            # translation & analysis
            title_ja  = translate_text_openai(title_en)
            abstract_ja = translate_text_openai(abstract_en)
            analysis_ja, tweet_ja = generate_analysis(title_ja, abstract_ja)

            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            cur.execute("""
              INSERT INTO papers
                (arxiv_id,title_en,title_ja,abstract_en,abstract_ja,
                 authors,categories,comment,published_at,
                 analysis_ja,tweet_ja,pdf_url,
                 created_at,translated_at)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (aid,title_en,title_ja,abstract_en,abstract_ja,
                  authors,categories,comment,pub_at,
                  analysis_ja,tweet_ja,pdf_url,
                  now,now))
        conn.commit()
    print("[fetch] end")

# ── Markdown ext -------------------------------------------------------
MD_EXT = ["fenced_code","tables","toc"]

# ── Index helpers ------------------------------------------------------
def _render_index(only_fav: bool):
    where = "WHERE favorite=1" if only_fav else ""
    with closing(get_db()) as c:
        rows = c.execute(f"""
            SELECT id,title_ja,favorite,analysis_ja,pdf_url
              FROM papers {where}
          ORDER BY created_at DESC
        """).fetchall()
    papers=[]
    for r in rows:
        html=markdown.markdown(r["analysis_ja"] or "",extensions=MD_EXT)
        papers.append({**dict(r),"analysis_html":html})
    return render_template("index.html", papers=papers, only_fav=only_fav)

# ── Routes -------------------------------------------------------------
@app.route("/")
def index(): return _render_index(False)

@app.route("/favorites")
def favorites(): return _render_index(True)

@app.route("/paper/<int:paper_id>")
def paper_detail(paper_id:int):
    with closing(get_db()) as c:
        p=c.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
        if not p: return redirect(url_for("index"))
        qa_rows=c.execute("""
              SELECT question, answer_md, created_at
                FROM qa
               WHERE paper_id=?
            ORDER BY created_at DESC
        """,(paper_id,)).fetchall()
    analysis_html=markdown.markdown(p["analysis_ja"] or "",extensions=MD_EXT)
    qa_list=[{
        "question":row["question"],
        "answer_html":markdown.markdown(row["answer_md"],extensions=MD_EXT),
        "created_at":row["created_at"].split("T")[0]
    } for row in qa_rows]
    return render_template("paper.html", paper=p,
                           analysis_html=analysis_html,
                           qa_list=qa_list)

# ── API: favorite ------------------------------------------------------
@app.route("/api/favorite/<int:paper_id>", methods=["POST"])
def api_favorite(paper_id:int):
    fav=1 if request.get_json(force=True).get("favorite") else 0
    with closing(get_db()) as c:
        c.execute("UPDATE papers SET favorite=? WHERE id=?", (fav,paper_id)); c.commit()
    return jsonify(ok=True,favorite=bool(fav)),200

# ── API: ask -----------------------------------------------------------
@app.route("/api/ask", methods=["POST"])
def api_ask():
    d=request.get_json(force=True); pid=int(d["paper_id"]); q=d["question"]
    with closing(get_db()) as c:
        paper=c.execute("SELECT * FROM papers WHERE id=?", (pid,)).fetchone()
        if not paper: return jsonify(error="paper not found"),404

    import openai
    answer_md=openai.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_NAME","gpt-4.1-mini"),
        messages=[
            {"role":"system","content":"日本語で Markdown 形式で回答してください"},
            {"role":"user","content":f"{paper['title_ja']}\n\n{paper['analysis_ja']}\n\n【質問】{q}"}
        ],
        temperature=0.3
    ).choices[0].message.content.strip()
    answer_html=markdown.markdown(answer_md,extensions=MD_EXT)

    with closing(get_db()) as c:
        c.execute("INSERT INTO qa (paper_id,question,answer_md) VALUES (?,?,?)",
                  (pid,q,answer_md)); c.commit()

    return jsonify(answer_html=answer_html, question=q),200

# ── CLI ----------------------------------------------------------------
if __name__=="__main__":
    import argparse,sys
    a=argparse.ArgumentParser(); a.add_argument("--init-db",action="store_true"); a.add_argument("--fetch",action="store_true")
    opt=a.parse_args(sys.argv[1:])
    if opt.init_db: init_db(); print("DB initialized.")
    elif opt.fetch: scheduled_fetch_job()
    else:
        if not os.path.exists(DB_PATH): init_db()
        app.run(debug=True,host="0.0.0.0",port=int(os.getenv("PORT",8000)))
