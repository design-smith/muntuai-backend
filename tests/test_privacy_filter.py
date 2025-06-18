import pytest
from backend.data_services.mongo.utils import privacy_filter
from backend.data_services.mongo.user_repository import list_users
from backend.data_services.mongo.contact_repository import list_contacts

class DummyCursor:
    def __init__(self, docs):
        self.docs = docs
    def limit(self, n):
        return self
    def __iter__(self):
        return iter(self.docs)

class DummyCollection:
    def __init__(self, docs):
        self.docs = docs
    def find(self, filter_dict):
        filtered = [d for d in self.docs if all(d.get(k) == v for k, v in filter_dict.items())]
        return DummyCursor(filtered)

def test_privacy_filter_applies_user_id():
    # Should add user_id to filter
    f = privacy_filter({}, "abc123")
    assert f["user_id"] == "abc123" or str(f["user_id"]) == "abc123"
    # Should not modify filter if user_id is None
    f2 = privacy_filter({"foo": 1}, None)
    assert f2["foo"] == 1

def test_list_users_privacy(monkeypatch):
    dummy = DummyCollection([{"user_id": "u1"}, {"user_id": "u2"}])
    monkeypatch.setattr("backend.data_services.mongo.user_repository.get_collection", lambda name: dummy)
    users = list_users(user_id="u1")
    assert all(u["user_id"] == "u1" for u in users)

def test_list_contacts_privacy(monkeypatch):
    dummy = DummyCollection([{"user_id": "u1"}, {"user_id": "u2"}])
    monkeypatch.setattr("backend.data_services.mongo.contact_repository.get_collection", lambda name: dummy)
    contacts = list_contacts(user_id="u2")
    assert all(c["user_id"] == "u2" for c in contacts) 