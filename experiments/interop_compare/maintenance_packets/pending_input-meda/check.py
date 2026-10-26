import sys
from pathlib import Path
sys.path.insert(0, '/workspace/scratch/bf91ba952a37/meda/experiments/interop_compare')
from maintenance import visible_check
raise SystemExit(visible_check(Path(__file__).resolve().parent))
