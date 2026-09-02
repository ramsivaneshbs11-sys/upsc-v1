"""
Quick backfill script — runs the pipeline for the last 3 days to catch up on missing data.
Run from the UPSC-Chatbot directory: python pipeline/run_backfill.py
"""
import sys
import os

# Ensure correct working directory so relative paths resolve
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

from pipeline.news_scheduler import run_pipeline, cleanup_old_data
from datetime import datetime, timedelta
import logging

log = logging.getLogger(__name__)

def backfill(days_back=3):
    """
    Runs the pipeline for the last X days to populate missing data.
    """
    print(f"Starting backfill for the last {days_back} days...")
    
    # Calculate dates to backfill (from oldest to newest)
    for i in range(days_back, -1, -1):
        target = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        print(f"\nRunning pipeline for {target}...")
        result = run_pipeline(target)
        print(f"    Result: {result}")

if __name__ == "__main__":
    print("=" * 60)
    print("UPSC News Pipeline — Backfill Mode")
    print("=" * 60)
    
    backfill(3)

    print("\n--- Cleaning up old data ---")
    cleanup_old_data()
    print("\n[Done] Backfill complete!")
