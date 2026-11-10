"""All reads and writes of run files. Swap this module to move to a database."""

import json
from pathlib import Path


def run_dir(client):
    path = Path("runs") / client
    (path / "screenshots").mkdir(parents=True, exist_ok=True)
    return path


def write_rows(client, name, rows):
    path = run_dir(client) / f"{name}.jsonl"
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return path


def read_rows(client, name):
    path = run_dir(client) / f"{name}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in open(path)]
