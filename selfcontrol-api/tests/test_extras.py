"""Tes PR/ujian dan pengaturan pribadi."""
API = "/api/v1"


def test_tasks_crud(client):
    r = client.post(f"{API}/tasks", json={"kind": "pr", "title": "Kimia bab 3", "due_date": "2026-11-25"})
    assert r.status_code == 201
    tid = r.json()["id"]
    client.post(f"{API}/tasks", json={"kind": "uj", "title": "SNBT", "due_date": "2026-11-23", "due_time": "08:00"})
    rows = client.get(f"{API}/tasks").json()
    assert [t["title"] for t in rows] == ["SNBT", "Kimia bab 3"]  # urut menurut tenggat
    assert rows[0]["due_time"] == "08:00"
    assert client.patch(f"{API}/tasks/{tid}", json={"done": True}).json()["done"] is True
    assert client.get(f"{API}/tasks").json()[-1]["title"] == "Kimia bab 3"  # yang selesai di bawah
    assert client.delete(f"{API}/tasks/{tid}").status_code == 204
    assert client.delete(f"{API}/tasks/{tid}").status_code == 404


def test_tasks_validation(client):
    assert client.post(f"{API}/tasks", json={"kind": "xx", "title": "Kimia", "due_date": "2026-11-25"}).status_code == 422
    assert client.post(f"{API}/tasks", json={"kind": "pr", "title": "a", "due_date": "2026-11-25"}).status_code == 422


def test_settings(client):
    assert client.get(f"{API}/settings").json() == {}
    assert client.put(f"{API}/settings", json={"name": "Daffa", "alloc": "40"}).json() == {"name": "Daffa", "alloc": "40"}
    assert client.put(f"{API}/settings", json={"name": "Budi"}).json()["name"] == "Budi"
    assert client.put(f"{API}/settings", json={"rahasia": "x"}).status_code == 422
    assert client.put(f"{API}/settings", json={"name": "x" * 41}).status_code == 413


def test_extras_need_api_key(client):
    assert client.get(f"{API}/tasks", headers={"X-API-Key": "salah"}).status_code == 401
