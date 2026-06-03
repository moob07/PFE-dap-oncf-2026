"""Connexion MongoDB Atlas (pymongo synchrone) + helpers d'accès."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

from . import config


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    if not config.MONGO_URI:
        raise RuntimeError("MONGO_URI non défini (variable d'environnement)")
    # maxPoolSize réduit : adapté aux clusters Atlas M0 (gratuit) et aux
    # environnements serverless (Vercel) où chaque instance ouvre un pool.
    return MongoClient(
        config.MONGO_URI,
        serverSelectionTimeoutMS=8000,
        connectTimeoutMS=8000,
        maxPoolSize=10,
        retryWrites=True,
        tz_aware=False,
    )


def get_db() -> Database:
    return get_client()[config.DB_NAME]


def next_id(name: str) -> int:
    """Compteur auto-incrément type séquence SQL via la collection `counters`."""
    db = get_db()
    doc = db.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return int(doc["seq"])


def set_counter(name: str, value: int) -> None:
    get_db().counters.update_one(
        {"_id": name}, {"$set": {"seq": value}}, upsert=True
    )


def clean(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Retire `_id` Mongo pour exposer des documents propres aux templates."""
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc
