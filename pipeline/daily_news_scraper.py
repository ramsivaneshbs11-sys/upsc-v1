import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from openai import OpenAI
import time
import schedule
from dotenv import load_dotenv

load_dotenv()

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = "upsc_chatbot"
COLLECTION_NAME = "current_affairs"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
JSON_DB_PATH = "backend/data/daily_news.json"
RETENTION_DAYS = 5

client = OpenAI(api_key=OPENAI_API_KEY)

def fetch_hindu_links():
    """Fetches top news links from The Hindu"""
    print("-> Fetching The Hindu links...")
    try:
        response = requests.get("https://www.thehindu.com/", timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/news/' in href:
                full_url = href if href.startswith('http') else 'https://www.thehindu.com' + href
                links.append(full_url)
        return list(set(links))[:8]
    except Exception as e:
        print(f"   ! Error fetching Hindu: {e}")
        return []

def fetch_pib_links():
    """Fetches links from Press Information Bureau"""
    print("-> Fetching PIB links...")
    try:
        response = requests.get("https://pib.gov.in/PressReleasePage.aspx", timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'PRID' in href:
                full_url = href if href.startswith('http') else 'https://pib.gov.in/' + href
                links.append(full_url)
        return list(set(links))[:8]
    except Exception as e:
        print(f"   ! Error fetching PIB: {e}")
        return []

def scrape_article(url):
    """Scrapes title and content from an article URL"""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1').get_text().strip() if soup.find('h1') else ""
        paragraphs = soup.find_all('p')
        content = " ".join([p.get_text().strip() for p in paragraphs])
        return {"title": title, "content": content[:3000], "url": url}
    except Exception as e:
        print(f"   ! Error scraping {url}: {e}")
        return None

def process_with_ai(articles, date):
    """Uses GPT-4o-mini to format articles into UPSC structure"""
    print(f"-> Processing AI Analysis for {date}...")
    if not OPENAI_API_KEY:
        print("   ! OPENAI_API_KEY not found. Skipping AI step.")
        return None

    prompt = f"""You are a UPSC Current Affairs Expert.
Convert the given news articles into a structured UPSC Daily News Analysis.

Date: {date}
Articles: {json.dumps(articles)}

Output ONLY valid JSON in this format:
{{
  "date": "{date}",
  "title": "News Analysis: {date}",
  "overview": "5-6 lines summary of entire content",
  "categories": {{
    "polity_governance": [],
    "international_relations": [],
    "economy": [],
    "science_technology": [],
    "environment_ecology": [],
    "defense_security": [],
    "government_schemes": []
  }},
  "source": "https://www.thehindu.com/"
}}

Instructions:
- Keep points crisp (1-2 lines)
- Use UPSC exam-oriented wording
- Group articles by category
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"   ! AI Error for {date}: {e}")
        return None

def cleanup_old_data():
    """Removes data older than RETENTION_DAYS from DB and local file"""
    threshold_date = (datetime.now() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    print(f"-> Cleaning up data older than {threshold_date}...")
    
    # 1. MongoDB Cleanup
    try:
        mongo_client = MongoClient(MONGODB_URI)
        db = mongo_client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        result = collection.delete_many({"date": {"$lt": threshold_date}})
        print(f"   ✓ Removed {result.deleted_count} old records from MongoDB.")
    except Exception as e:
        print(f"   ! MongoDB cleanup error: {e}")

    # 2. Local JSON Cleanup
    try:
        if os.path.exists(JSON_DB_PATH):
            with open(JSON_DB_PATH, 'r') as f:
                db_content = json.load(f)
            
            original_count = len(db_content)
            db_content = {d: v for d, v in db_content.items() if d >= threshold_date}
            
            if len(db_content) < original_count:
                with open(JSON_DB_PATH, 'w') as f:
                    json.dump(db_content, f, indent=2)
                print(f"   ✓ Removed {original_count - len(db_content)} old records from JSON file.")
    except Exception as e:
        print(f"   ! File cleanup error: {e}")

def store_data(data):
    """Stores data in MongoDB and local JSON file"""
    print(f"-> Storing data for {data['date']}...")
    try:
        mongo_client = MongoClient(MONGODB_URI)
        db = mongo_client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        collection.update_one({"date": data["date"]}, {"$set": data}, upsert=True)
    except Exception as e:
        print(f"   ! MongoDB storage error: {e}")

    try:
        os.makedirs(os.path.dirname(JSON_DB_PATH), exist_ok=True)
        db_content = {}
        if os.path.exists(JSON_DB_PATH):
            with open(JSON_DB_PATH, 'r') as f:
                db_content = json.load(f)
        
        db_content[data["date"]] = data
        with open(JSON_DB_PATH, 'w') as f:
            json.dump(db_content, f, indent=2)
    except Exception as e:
        print(f"   ! File storage error: {e}")

def run_pipeline_for_date(target_date):
    """Runs the pipeline for a specific date (YYYY-MM-DD)"""
    links = fetch_hindu_links() + fetch_pib_links()
    if not links: return

    articles = []
    for link in links[:10]: # Limit articles per day for AI budget
        article = scrape_article(link)
        if article: articles.append(article)
    
    if articles:
        formatted_data = process_with_ai(articles, target_date)
        if formatted_data:
            store_data(formatted_data)
            return True
    return False

def backfill_past_days():
    """Initially collects data for the past 5 days"""
    print(f"\n[BACKFILL] Starting collection for past {RETENTION_DAYS} days...")
    for i in range(RETENTION_DAYS - 1, -1, -1):
        target_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        print(f"\n-> Processing backfill for {target_date}...")
        run_pipeline_for_date(target_date)
    print("\n[BACKFILL] Completed.")

def daily_job():
    """Daily routine: cleanup and current news scrape"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Daily Sync...")
    cleanup_old_data()
    today = datetime.now().strftime("%Y-%m-%d")
    run_pipeline_for_date(today)
    print("✓ Daily Sync Successful.")

if __name__ == "__main__":
    # 1. Backfill past 5 days on first launch
    backfill_past_days()
    
    # 2. Cleanup immediately
    cleanup_old_data()
    
    # 3. Schedule daily at 6:00 AM
    print("\nScheduler active. Waiting for 06:00 daily...")
    schedule.every().day.at("06:00").do(daily_job)
    
    while True:
        schedule.run_pending()
        time.sleep(60)
