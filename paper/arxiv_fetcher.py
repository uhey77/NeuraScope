import feedparser
from datetime import datetime
import pytz # タイムゾーン対応のため

ARXIV_RSS_BASE_URL = "http://export.arxiv.org/rss/"

def fetch_arxiv_papers(category="cs.AI", max_results=10):
    """
    指定されたarXivカテゴリの最新論文情報をRSSフィードから取得する。

    Args:
        category (str): arXivのカテゴリ (例: "cs.AI", "cs.LG", "cs.CV")。
        max_results (int): 取得する論文の最大数。

    Returns:
        list: 論文情報の辞書のリスト。各辞書は以下のキーを持つ:
              'title', 'authors', 'published_date', 'summary', 'link_arxiv', 'link_pdf'
    """
    feed_url = f"{ARXIV_RSS_BASE_URL}{category}"
    feed = feedparser.parse(feed_url)

    papers = []
    for entry in feed.entries[:max_results]:
        # 著者情報はリストになっている場合があるので、文字列に結合
        authors = ", ".join(author.name for author in entry.authors)

        # published_parsedからdatetimeオブジェクトを生成し、タイムゾーンをUTCに設定
        # その後、日本のタイムゾーンに変換（表示のため）
        published_dt_utc = datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
        jst = pytz.timezone('Asia/Tokyo')
        published_dt_jst = published_dt_utc.astimezone(jst)
        published_date_str = published_dt_jst.strftime('%Y-%m-%d %H:%M:%S %Z') # JSTを明示

        # PDFリンクを探す
        pdf_link = None
        for link in entry.links:
            if link.get('title') == 'pdf':
                pdf_link = link.href
                break
        
        papers.append({
            'title': entry.title,
            'authors': authors,
            'published_date': published_date_str,
            'summary': entry.summary, # HTMLタグが含まれている場合がある
            'link_arxiv': entry.link, # arXivの論文ページへのリンク
            'link_pdf': pdf_link
        })
    return papers

if __name__ == '__main__':
    # テスト用: cs.AIカテゴリの最新5件の論文を取得して表示
    ai_papers = fetch_arxiv_papers(category="cs.AI", max_results=5)
    for i, paper in enumerate(ai_papers):
        print(f"--- Paper {i+1} ---")
        print(f"Title: {paper['title']}")
        print(f"Authors: {paper['authors']}")
        print(f"Published: {paper['published_date']}")
        print(f"Summary (first 200 chars): {paper['summary'][:200]}...")
        print(f"arXiv Link: {paper['link_arxiv']}")
        print(f"PDF Link: {paper['link_pdf']}")
        print("-" * 20)

    lg_papers = fetch_arxiv_papers(category="cs.LG", max_results=3)
    print("\n--- cs.LG Papers ---")
    for paper in lg_papers:
        print(paper['title'])
