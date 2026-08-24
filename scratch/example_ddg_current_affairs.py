from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup
import json

def fetch_current_affairs(query: str, max_articles: int = 3):
    print(f"Searching news for: '{query}'...")
    articles = []
    
    # 1. Fetch search results from DDG News
    # timelimit='m' (last month), 'w' (last week), 'd' (last day)
    try:
        with DDGS() as ddgs:
            news_results = list(ddgs.news(query, max_results=max_articles, timelimit="w"))
    except Exception as e:
        print(f"Error fetching from DDG: {e}")
        return []
        
    # 2. Extract detail from each URL
    for idx, item in enumerate(news_results):
        url = item.get("url")
        title = item.get("title")
        snippet = item.get("body")
        source = item.get("source")
        pub_date = item.get("date")
        
        print(f"\n[{idx+1}] Title: {title}")
        print(f"    Source: {source} | Date: {pub_date}")
        print(f"    URL: {url}")
        
        # Scrape the full website content
        full_text = ""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            # Timeout of 10s to avoid hanging
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                
                # Simple heuristic to extract main text from paragraphs
                # (You can fine-tune this for specific news sites or use a specialized library)
                paragraphs = soup.find_all("p")
                full_text = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])
                print(f"    Successfully scraped full text ({len(full_text)} chars)")
            else:
                print(f"    Failed to fetch full page: HTTP {response.status_code}")
        except Exception as e:
            print(f"    Error scraping {url}: {e}")
            
        articles.append({
            "title": title,
            "snippet": snippet,
            "url": url,
            "source": source,
            "date": pub_date,
            "full_content": full_text
        })
        
    return articles

if __name__ == "__main__":
    # Example: Search for UPSC UPSC-related current affairs in the last week
    results = fetch_current_affairs("UPSC Civil Services", max_articles=2)
