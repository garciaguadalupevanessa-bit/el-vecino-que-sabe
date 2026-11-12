"""Loads the aid base at startup (Postgres if DATABASE_URL is set; otherwise the JSON files).
If the data is invalid the service fails to start with a clear message."""
from app.core import config
from app.data.sources import InvalidData, load_from_db, load_from_json, validate

DATA_SOURCE = "postgres" if config.DATABASE_URL else "json"


def _load():
    try:
        if config.DATABASE_URL:
            return load_from_db(config.DATABASE_URL, config.SEED_ON_START)
        return load_from_json()
    except InvalidData as e:
        raise SystemExit(str(e))


AIDS, AIDS_BY_ID, BLOCKS = _load()


def refresh_from_database() -> None:
    """Refresh shared catalog objects after agent publication or source invalidation."""
    if not config.DATABASE_URL:
        return
    from app.db import database as db

    with db.connect(config.DATABASE_URL) as conn:
        aids, aids_by_id, blocks = validate(db.read_aids(conn), db.read_blocks(conn))
    AIDS[:] = aids
    AIDS_BY_ID.clear()
    AIDS_BY_ID.update(aids_by_id)
    BLOCKS.clear()
    BLOCKS.update(blocks)
