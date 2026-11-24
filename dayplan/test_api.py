import os
import tempfile

fd, path = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["DATABASE_PATH"] = path

from app import app  # noqa: E402
from database import init_db  # noqa: E402


def run_tests():
    init_db()
    client = app.test_client()

    response = client.post("/api/tasks", json={
        "title": "Prepare demo",
        "description": "Finish backend demo",
        "due_date": "2026-11-25",
        "priority": "high"
    })
    assert response.status_code == 201, response.get_json()
    task = response.get_json()

    response = client.get("/api/tasks?priority=high")
    assert response.status_code == 200
    assert response.get_json()["count"] == 1

    response = client.patch(f"/api/tasks/{task['id']}", json={"status": "completed"})
    assert response.status_code == 200
    assert response.get_json()["status"] == "completed"

    response = client.get("/api/summaries/weekly?start=2026-11-24")
    assert response.status_code == 200

    response = client.delete(f"/api/tasks/{task['id']}")
    assert response.status_code == 204
    print("All API tests passed.")


if __name__ == "__main__":
    try:
        run_tests()
    finally:
        if os.path.exists(path):
            os.remove(path)
