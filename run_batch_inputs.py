"""Backward-compatibility forwarder shim. Forwards to scripts/run_batch_inputs.py."""
import sys
import subprocess
from pathlib import Path

target = Path(__file__).parent / "scripts" / "run_batch_inputs.py"
if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, str(target)] + sys.argv[1:]))
