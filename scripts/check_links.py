"""Check that every course link in data/catalog.yaml still opens (run before the demo).

    uv run python scripts/check_links.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from core.taxonomy import load_catalog  # noqa: E402

bad = 0
with httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": "Mozilla/5.0"}) as client:
    for item in load_catalog():
        try:
            status = client.get(item.url).status_code
        except httpx.HTTPError as exc:
            status = f"error: {exc.__class__.__name__}"
        ok = status == 200
        bad += not ok
        print(f"{'OK ' if ok else 'BAD'} {status}  {item.platform:15} {item.title}  {item.url}")
print(f"\n{bad} link(s) need fixing" if bad else "\nAll links OK")
sys.exit(1 if bad else 0)
