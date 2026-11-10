"""Where finished runs live: a bucket on the server, a folder on a laptop."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

BUCKET = os.environ.get("RUNS_BUCKET")
LOCAL = Path("runs/_live")


def _bucket():
    from google.cloud import storage
    return storage.Client().bucket(BUCKET)


def put(path, data, content_type):
    if BUCKET:
        _bucket().blob(path).upload_from_string(data, content_type=content_type)
        return
    target = LOCAL / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data if isinstance(data, bytes) else data.encode())


def get(path):
    if BUCKET:
        blob = _bucket().blob(path)
        return blob.download_as_bytes() if blob.exists() else None
    target = LOCAL / path
    return target.read_bytes() if target.exists() else None


def take_daily_slot(limit):
    """Count today's runs. A cap on spend, so being off by one under load is fine."""
    path = f"counters/{datetime.now(timezone.utc):%Y-%m-%d}.json"
    used = json.loads(get(path) or b"0")
    if used >= limit:
        return False
    put(path, json.dumps(used + 1), "application/json")
    return True
