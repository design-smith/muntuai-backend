from bson import ObjectId
from datetime import datetime

def to_objectid(val):
    if isinstance(val, ObjectId):
        return val
    if isinstance(val, str) and len(val) == 24:
        try:
            return ObjectId(val)
        except Exception:
            pass
    return val

def to_datetime(val):
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            # Accepts ISO8601 and Zulu time
            return datetime.fromisoformat(val.replace('Z', '+00:00'))
        except Exception:
            pass
    return val

def privacy_filter(filter_dict, user_id, user_field="user_id"):
    """
    Enforce user-level privacy by adding a user_id filter to the query.
    If user_id is None, returns the filter unchanged (for admin/system use).
    """
    if user_id is not None:
        filter_dict = dict(filter_dict) if filter_dict else {}
        filter_dict[user_field] = to_objectid(user_id)
    return filter_dict 