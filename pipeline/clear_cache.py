import json

def clear_date():
    with open('backend/data/daily_news.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for date in ['2026-05-06', '2026-05-07', '2026-05-08', '2026-05-09']:
        if date in data:
            del data[date]
            print(f"Cleared {date} cache.")
        
    with open('backend/data/daily_news.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    clear_date()
