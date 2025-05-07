DROP TABLE IF EXISTS favorites;
DROP TABLE IF EXISTS articles;

CREATE TABLE articles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  arxiv_id TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  authors TEXT,
  published_date_str TEXT, -- JSTに変換した文字列で保存
  published_ts INTEGER, -- UNIXタイムスタンプ (ソート用)
  summary TEXT,
  link_arxiv TEXT NOT NULL,
  link_pdf TEXT,
  category TEXT NOT NULL, -- どのカテゴリで取得したか
  fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  translated_title_ja TEXT,
  translated_summary_ja TEXT
);
CREATE INDEX idx_articles_category_published_ts ON articles (category, published_ts DESC);
CREATE INDEX idx_articles_arxiv_id ON articles (arxiv_id);


CREATE TABLE favorites (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  arxiv_id TEXT NOT NULL UNIQUE, -- 論文のarXiv ID (例: 2303.12345)
  title TEXT NOT NULL,
  link_arxiv TEXT NOT NULL,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (arxiv_id) REFERENCES articles(arxiv_id) ON DELETE CASCADE -- articlesから削除されたらお気に入りも削除
);
CREATE INDEX idx_favorites_arxiv_id ON favorites (arxiv_id);