"""Loads (upserts) aids.json and blocks.json into Postgres.

Usage:  python -m app.db.seed
        docker compose run --rm backend python -m app.db.seed
"""
import argparse
import sys

from app.core import config
from app.data.sources import InvalidData, read_json, validate
from app.db import database as db


def main() -> None:
    parser = argparse.ArgumentParser(description="Loads the JSON aids into Postgres.")
    parser.add_argument("--url", default=config.DATABASE_URL, help="DATABASE_URL (defaults to the environment one)")
    args = parser.parse_args()
    if not args.url:
        sys.exit("DATABASE_URL is missing.")

    raw, blocks = read_json()
    try:
        normalized_aids, _, normalized_blocks = validate(raw, blocks)
    except InvalidData as e:
        sys.exit(str(e))

    with db.connect(args.url) as conn:
        db.create_schema(conn)
        db.upsert_blocks(conn, normalized_blocks)
        db.upsert_aids(conn, normalized_aids)
        conn.commit()
    print(f"{len(normalized_aids)} aids and {len(normalized_blocks)} blocks loaded.")


if __name__ == "__main__":
    main()
