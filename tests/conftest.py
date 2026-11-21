"""Tests run against a throwaway project root (config copy, synthetic ledger, its own git repo with a
rules-v1 tag) and a throwaway data dir, so they never touch real data or spend anything."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_TMP = Path(tempfile.mkdtemp(prefix="xrf-test-"))
ROOT = _TMP / "root"
(ROOT / "docs").mkdir(parents=True)
shutil.copytree(REPO / "config", ROOT / "config")
(ROOT / "config" / "run_state.json").unlink(missing_ok=True)
shutil.copy(REPO / "RULES.md", ROOT / "RULES.md")
(ROOT / "docs" / "DECISIONS.md").write_text("# test decisions\n")
for d in ("ledger", "cohort", "audit", "report", "prospective"):
    (ROOT / d).mkdir()
shutil.copy(REPO / "tests" / "fixtures" / "releases.csv", ROOT / "ledger" / "releases.csv")
shutil.copy(REPO / "tests" / "fixtures" / "signals.csv", ROOT / "ledger" / "signals.csv")
subprocess.run(["git", "init", "-q", str(ROOT)], check=True)
subprocess.run(["git", "-C", str(ROOT), "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], check=True)
subprocess.run(["git", "-C", str(ROOT), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], check=True)
subprocess.run(["git", "-C", str(ROOT), "tag", "rules-v1"], check=True)
subprocess.run(["git", "-C", str(ROOT), "config", "user.email", "t@t"], check=True)
subprocess.run(["git", "-C", str(ROOT), "config", "user.name", "t"], check=True)

os.environ["XRF_ROOT"] = str(ROOT)
os.environ["XRF_DATA"] = str(_TMP / "data")
os.environ.pop("XRF_OFFLINE", None)
os.environ["X_BEARER_TOKEN"] = "test-not-real"
os.environ["ANTHROPIC_API_KEY"] = "test-not-real"
# Grok discovery is not faked: never let a real xAI key reach the tests (they would make paid calls).
os.environ.pop("XAI_API_KEY", None)
