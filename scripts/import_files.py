"""Add the pages already on disk to the database, without indexing them again.

    python -m scripts.import_files [--tag NAME ...]

Pages that have no row yet get one, with the named tags (created if missing). The tags in the
database are then copied onto the index, so this also repairs an index whose tags have drifted.
"""

import argparse

from qdrant_client import QdrantClient

from app.config import Settings
from app.core.database import make_sessions
from app.services import file_service
from app.services.store_service import Store

parser = argparse.ArgumentParser()
parser.add_argument("--tag", action="append", default=[])
args = parser.parse_args()

settings = Settings.from_env()
store = Store(QdrantClient(url=settings.qdrant_url, timeout=300), settings.collection)
with make_sessions(settings.database_url)() as db:
    print(f"Added {file_service.import_files(settings, db, store, args.tag)} files")
