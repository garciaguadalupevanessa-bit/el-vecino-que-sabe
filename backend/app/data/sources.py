"""Reading and validating the aid base (JSON or Postgres). Nothing is loaded on import."""
import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.models.aid import Aid, Requirement

log = logging.getLogger("elvecinoquesabe.data")
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class InvalidData(ValueError):
    """The aid base does not match the schema or has broken references."""


def read_json() -> tuple[list[dict], dict]:
    raw = json.loads((DATA_DIR / "aids.json").read_text(encoding="utf-8"))
    blocks = json.loads((DATA_DIR / "blocks.json").read_text(encoding="utf-8"))
    return raw, blocks


def validate(raw_aids: list[dict], blocks: dict):
    try:
        for reqs in blocks.values():
            for r in reqs:
                Requirement(**r)
        aids = [Aid(**a) for a in raw_aids]
    except ValidationError as e:
        raise InvalidData(f"Invalid aid base:\n{e}") from e

    ids = {a.id for a in aids}
    if len(ids) != len(aids):
        raise InvalidData("There are duplicated aid ids.")
    for a in aids:
        for r in a.requirements:
            if r.ref and r.ref not in blocks:
                raise InvalidData(f"{a.id}: block '{r.ref}' does not exist.")
            if a.reliability == "verified" and r.ref:
                for block_requirement in blocks[r.ref]:
                    parsed = Requirement(**block_requirement)
                    if parsed.field and (parsed.needs_verification or parsed.citation is None):
                        raise InvalidData(
                            f"{a.id}: referenced block '{r.ref}' contains an evaluable rule without an approved citation."
                        )
        for alt in a.alternatives:
            if alt not in ids:
                raise InvalidData(f"{a.id}: alternative '{alt}' does not exist.")

    dumped = [a.model_dump(mode="json") for a in aids]
    return dumped, {a["id"]: a for a in dumped}, blocks


def load_from_json():
    raw, blocks = read_json()
    return validate(raw, blocks)


def load_from_db(url: str, seed: bool = True):
    from app.db import database as db  # lazy import: JSON mode does not need psycopg

    with db.connect(url) as conn:
        db.create_schema(conn)
        if seed and db.count_aids(conn) == 0:
            raw, blocks = read_json()
            normalized_aids, _, normalized_blocks = validate(raw, blocks)
            db.upsert_blocks(conn, normalized_blocks)
            db.upsert_aids(conn, normalized_aids)
            conn.commit()
            log.info("Database seeded with %d aids from the JSON files.", len(raw))
        raw = db.read_aids(conn)
        blocks = db.read_blocks(conn)
    return validate(raw, blocks)
