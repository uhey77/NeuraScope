PRAGMA foreign_keys = ON;

-- 論文本体 ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS papers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    arxiv_id        TEXT    NOT NULL UNIQUE,
    title_en        TEXT    NOT NULL,
    title_ja        TEXT,
    abstract_en     TEXT    NOT NULL,
    abstract_ja     TEXT,
    authors         TEXT,               -- カンマ区切り
    categories      TEXT,               -- スペース区切り
    comment         TEXT,
    published_at    DATETIME,
    analysis_ja     TEXT,               -- 8項目 Markdown
    tweet_ja        TEXT,               -- 140 字ツイート
    pdf_url         TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    translated_at   DATETIME,
    favorite        INTEGER DEFAULT 0
);

-- Q&A 履歴 ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qa (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id    INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    question    TEXT    NOT NULL,
    answer_md   TEXT    NOT NULL,       -- 回答を Markdown 原文で保持
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_qa_paper_id      ON qa(paper_id);
CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id  ON papers(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_papers_created_at ON papers(created_at);
CREATE INDEX IF NOT EXISTS idx_papers_favorite  ON papers(favorite);
