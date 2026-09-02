"""Backward-compatibility forwarder shim. Forwards to scripts/ingest_to_qdrant.py."""
import sys
import subprocess
from pathlib import Path

target = Path(__file__).parent / "scripts" / "ingest_to_qdrant.py"
if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, str(target)] + sys.argv[1:]))
