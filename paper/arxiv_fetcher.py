import feedparser
from datetime import datetime
import pytz
import requests

ARXIV_RSS_BASE_URL = "http://export.arxiv.org/rss/"

class ArxivFetchError(Exception):
    """arXivからの情報取得エラー用のカスタム例外"""
    pass

def fetch_arxiv_papers(category="cs.AI", max_results=10, timeout=10):
    """
    指定されたarXivカテゴリの最新論文情報をRSSフィードから取得する。
    ネットワークエラーやパースエラーを考慮。

    Args:
        category (str): arXivのカテゴリ (例: "cs.AI", "cs.LG", "cs.CV")。
        max_results (int): 取得する論文の最大数。
        timeout (int): リクエストのタイムアウト秒数。

    Returns:
        list: 論文情報の辞書のリスト。各辞書は以下のキーを持つ:
              'arxiv_id', 'title', 'authors', 'published_date', 'summary', 'link_arxiv', 'link_pdf'
    """
    feed_url = f"{ARXIV_RSS_BASE_URL}{category}"
    papers = []

    try:
        response = requests.get(feed_url, timeout=timeout)
        response.raise_for_status()  # HTTPエラーがあれば例外を発生させる (4xx, 5xx)
        
        feed = feedparser.parse(response.content)

        if feed.bozo:
            print(f"Warning: feedparser encountered an issue for {category}: {feed.bozo_exception}")
            # エラーが深刻な場合は ArxivFetchError を raise する選択肢もある

        if not feed.entries:
            print(f"No entries found for category: {category}")
            return []

        for entry in feed.entries[:max_results]:
            authors = ", ".join(author.name for author in entry.authors)
            
            published_dt_utc = datetime.now(pytz.utc) # デフォルト値
            if entry.published_parsed:
                try:
                    published_dt_utc = datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
                except Exception:
                    pass # パース失敗時はデフォルト値のまま

            jst = pytz.timezone('Asia/Tokyo')
            published_dt_jst = published_dt_utc.astimezone(jst)
            published_date_str = published_dt_jst.strftime('%Y-%m-%d %H:%M:%S %Z')

            pdf_link = None
            for link_obj in entry.links:
                if link_obj.get('type') == 'application/pdf' or link_obj.get('title') == 'pdf':
                    pdf_link = link_obj.href
                    break
            
            arxiv_id_full = entry.link.split('/')[-1]
            arxiv_id = arxiv_id_full.split('v')[0] # バージョン情報を除去 (例: 2303.12345v1 -> 2303.12345)

            papers.append({
                'arxiv_id': arxiv_id,
                'title': entry.title,
                'authors': authors,
                'published_date': published_date_str, # JSTに変換した文字列
                'summary': entry.summary,
                'link_arxiv': entry.link,
                'link_pdf': pdf_link
            })
            
    except requests.exceptions.RequestException as e:
        raise ArxivFetchError(f"Network error fetching arXiv feed for {category}: {e}")
    except Exception as e:
        # feedparserのパースエラーや予期せぬエラー
        raise ArxivFetchError(f"Error processing arXiv feed for {category}: {e}")
        
    return papers

if __name__ == '__main__':
    # pip install requests pytz feedparser を実行してください
    try:
        print("--- Testing cs.AI (first 2 papers) ---")
        ai_papers = fetch_arxiv_papers(category="cs.AI", max_results=2)
        for paper in ai_papers:
            print(f"  ID: {paper['arxiv_id']}")
            print(f"  Title: {paper['title']}")
            print(f"  Published (JST): {paper['published_date']}")
            print("-" * 10)
        
        print("\n--- Testing cs.LG (first 1 paper) ---")
        lg_papers = fetch_arxiv_papers(category="cs.LG", max_results=1)
        for paper in lg_papers:
            print(f"  ID: {paper['arxiv_id']}")
            print(f"  Title: {paper['title']}")
            print("-" * 10)

        # エラーテスト (存在しないカテゴリ)
        print("\n--- Testing non.existent category ---")
        error_papers = fetch_arxiv_papers(category="non.existent.category", max_results=2)
        if not error_papers:
            print("  No papers found, as expected.")

    except ArxivFetchError as e:
        print(f"An error occurred during testing: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during testing: {e}")
