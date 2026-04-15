"""
Rotate the dashboard access password.

Usage:
    python set_password.py NEW_PASSWORD

Updates the GATE_HASH constant inside dashboard.html in place.
Remember to commit + push after running this so the live site picks it up.
"""
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
DASHBOARD = HERE / "dashboard.html"


def main():
    if len(sys.argv) != 2:
        print("Usage: python set_password.py NEW_PASSWORD")
        sys.exit(1)

    new_password = sys.argv[1]
    new_hash = hashlib.sha256(new_password.encode("utf-8")).hexdigest()

    html = DASHBOARD.read_text(encoding="utf-8")
    pattern = r'const GATE_HASH = "[a-f0-9]{64}";'
    replacement = f'const GATE_HASH = "{new_hash}";'

    if not re.search(pattern, html):
        print("ERROR: could not find GATE_HASH line in dashboard.html")
        sys.exit(2)

    new_html = re.sub(pattern, replacement, html, count=1)
    DASHBOARD.write_text(new_html, encoding="utf-8")

    print(f"Password updated. New hash: {new_hash}")
    print("Don't forget to commit + push so the live site picks it up:")
    print('  git add dashboard.html && git commit -m "Rotate password" && git push')


if __name__ == "__main__":
    main()
