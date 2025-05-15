PRAGMA foreign_keys = ON;

-- ────────── arXiv 論文テーブル
CREATE TABLE IF NOT EXISTS papers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    arxiv_id        TEXT NOT NULL UNIQUE,
    title_en        TEXT NOT NULL,
    title_ja        TEXT,
    abstract_en     TEXT NOT NULL,
    abstract_ja     TEXT,
    authors         TEXT,
    categories      TEXT,
    comment         TEXT,
    published_at    DATETIME,
    analysis_ja     TEXT,
    tweet_ja        TEXT,
    pdf_url         TEXT,
    favorite        INTEGER DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    translated_at   DATETIME
);

-- ────────── 外部フィード
CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title_en    TEXT NOT NULL,
    title_ja    TEXT,
    link        TEXT NOT NULL UNIQUE,
    summary_en  TEXT,
    summary_ja  TEXT,
    published   DATETIME,
    source_id   TEXT,
    category    TEXT,          -- paper | news | blog
    favorite    INTEGER DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ────────── Q&A（論文詳細ページ用）
CREATE TABLE IF NOT EXISTS qa (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id   INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    question   TEXT NOT NULL,
    answer_md  TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ────────── Q&A（外部フィード記事用）
CREATE TABLE IF NOT EXISTS article_qa (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    question    TEXT NOT NULL,
    answer_md   TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_papers_fav   ON papers(favorite);
CREATE INDEX IF NOT EXISTS idx_articles_cat ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_fav ON articles(favorite);
