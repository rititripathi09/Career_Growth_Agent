"""Reset the database and load the Nimbus Tech demo data.

    uv run python scripts/seed.py
    uv run python scripts/seed.py --db other.db
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import db  # noqa: E402
from core.seed import seed  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(db.DB_PATH))
    args = parser.parse_args()
    conn = db.connect(args.db)
    seed(conn)
    n = conn.execute("SELECT COUNT(*) FROM employee").fetchone()[0]
    print(f"Seeded {n} employees into {args.db}")
