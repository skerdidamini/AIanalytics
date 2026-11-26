"""Create a consistent SQLite snapshot while the service is running."""
import argparse
import os
from pathlib import Path
import sqlite3
import tempfile
from contextlib import closing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    destination = args.destination
    source_uri = args.source.resolve().as_uri() + "?mode=ro"

    # Publish only a complete snapshot, without overwriting any earlier copy.
    with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
        snapshot = Path(directory) / "backup.sqlite3"
        with closing(sqlite3.connect(source_uri, uri=True)) as source:
            with closing(sqlite3.connect(snapshot)) as target:
                source.backup(target)
                target.execute("PRAGMA journal_mode=DELETE")
                if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise RuntimeError("SQLite snapshot failed its integrity check")
        snapshot.chmod(0o600)
        os.link(snapshot, destination)


if __name__ == "__main__":
    main()
