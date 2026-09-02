"""
run_eval_sequential.py
──────────────────────
Runs evaluation for the primary BGE-Base embedding model.
"""

import sys
import os
import gc
import json
from pathlib import Path

# Add workspace directory to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import evaluate_embeddings
from evaluate_embeddings import ALL_EVAL_MODELS, evaluate_embedding_models

def main():
    print("=" * 80)
    print("     STARTING SEQUENTIAL EMBEDDING EVALUATION BENCHMARK     ")
    print("=" * 80)

    for m in ALL_EVAL_MODELS:
        key = m["id_key"]
        print(f"\n--- Running evaluation for model key: {key} ---")
        try:
            evaluate_embedding_models(selected_model_key=key)
        except Exception as exc:
            print(f"Error evaluating {key}: {exc}")
        
        # Force garbage collection to free RAM
        gc.collect()

    print("\nBenchmark pipeline execution complete.")

if __name__ == "__main__":
    main()
