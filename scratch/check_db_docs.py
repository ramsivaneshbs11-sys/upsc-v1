import sys
from pathlib import Path
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/upsc_rag"

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # Check total rows in documents
        res = conn.execute(text("SELECT count(*), status FROM documents GROUP BY status"))
        rows = res.fetchall()
        print("Document count by status in PostgreSQL:")
        for r in rows:
            print(f"  {r[1]}: {r[0]} documents")
            
        res_total = conn.execute(text("SELECT count(*) FROM documents"))
        print(f"Total documents registered: {res_total.fetchone()[0]}")
        
        # Check classification counts
        res_class = conn.execute(text("SELECT count(*), classification FROM documents GROUP BY classification"))
        print("\nDocument count by classification:")
        for r in res_class.fetchall():
            print(f"  {r[1]}: {r[0]} documents")
            
except Exception as e:
    print(f"Failed to query database: {e}")
