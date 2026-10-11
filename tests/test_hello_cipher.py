"""Test written by the Cipher test-writer specialist (spawned sub-agent)."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "artifacts" / "hello.py"


def test_hello_script_prints_greeting():
    assert SCRIPT.is_file(), f"missing artifact: {SCRIPT}"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=30, cwd=str(REPO),
    )
    assert proc.returncode == 0, f"non-zero exit: {proc.stderr[-500:]}"
    assert "Hello, Cipher!" in proc.stdout, f"unexpected stdout: {proc.stdout!r}"


if __name__ == "__main__":
    test_hello_script_prints_greeting()
    print("test_hello_cipher: PASS")
