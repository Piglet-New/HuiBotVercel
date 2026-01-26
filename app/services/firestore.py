from __future__ import annotations

from functools import lru_cache

from app.config import load_settings


@lru_cache(maxsize=1)
def get_client():
    from google.cloud import firestore

    settings = load_settings()
    return firestore.Client(project=settings.gcp_project_id)


def server_timestamp():
    from google.cloud import firestore

    return firestore.SERVER_TIMESTAMP
