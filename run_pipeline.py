"""Backward-compatibility forwarder shim. Forwards to scripts/run_pipeline.py."""
import sys
import subprocess
from pathlib import Path

target = Path(__file__).parent / "scripts" / "run_pipeline.py"
if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, str(target)] + sys.argv[1:]))
