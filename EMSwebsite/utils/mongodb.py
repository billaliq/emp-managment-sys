from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from django.conf import settings

_client = None
_db = None


def get_mongo_client():
    global _client
    if _client is None:
        if not settings.MONGODB_URI:
            raise ValueError("MONGODB_URI is not set in environment variables.")
        _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_mongo_db():
    global _db
    if _db is None:
        client = get_mongo_client()
        _db = client[settings.MONGODB_DB_NAME]
    return _db


def get_collection(collection_name: str):
    return get_mongo_db()[collection_name]


def test_connection():
    try:
        client = get_mongo_client()
        client.admin.command('ping')
        return True, "Connected to MongoDB Atlas successfully."
    except ConnectionFailure as e:
        return False, f"MongoDB connection failed: {e}"
