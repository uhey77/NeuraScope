# feeds.py  ────────────────────────────────────────────────────────────
FEEDS = {
    # ---------- 論文フィード（HTML scrape） --------------------------
    "hf_daily": {
        "name": "Hugging Face - Daily Papers",
        "url":  "https://huggingface.co/papers",
        "category": "paper",
        "scrape": "hf",
    },
    "pwc_trend": {
        "name": "Papers with Code - Trending",
        "url":  "https://paperswithcode.com",
        "category": "paper",
        "scrape": "pwc",
    },

    # ---------- Reddit（blog） --------------------------------------
    "reddit_llama":  { "name":"Reddit r/LocalLLaMA",         "url":"https://www.reddit.com/r/LocalLLaMA/.rss",          "category":"blog" },
    "reddit_ml":     { "name":"Reddit r/MachineLearning",    "url":"https://www.reddit.com/r/MachineLearning/.rss",     "category":"blog" },
    "reddit_prompt": { "name":"Reddit r/aipromptprogramming","url":"https://www.reddit.com/r/aipromptprogramming/.rss", "category":"blog" },

    # ---------- 技術ブログ / ニュース -------------------------------
    "github_trending": {
        "name": "GitHub Trending",
        "url":  "https://github.com/trending?since=daily",
        "category": "blog",
        "scrape": "gh",
    },
    "dlai_batch": {
        "name": "The Batch - deeplearning.ai",
        "url":  "https://www.deeplearning.ai/the-batch/",
        "category": "news",
        "scrape": "batch",
    },
    "simon_blog": { "name":"Simon Willison's Weblog","url":"https://simonwillison.net/atom/everything/","category":"blog"},
    "lil_log":    { "name":"Lil'Log",                "url":"https://lilianweng.github.io/index.xml",      "category":"blog"},
    "nlp_news":   { "name":"NLP Newsletter",         "url":"https://nlpnewsletter.substack.com/feed",      "category":"news"},
}
