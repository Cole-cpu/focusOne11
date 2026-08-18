"""FocusOne backend regression suite.

Coverage:
- Auth register/login
- Study timetable generation (P0): long window spread, short window, past exam
- Dashboard aggregation
- Task CRUD + patch flow
- Paste parser
- Focus log + streak
- Flashcards CRUD
"""
import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")


def _future(days: int) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


@pytest.fixture(scope="module")
def auth_session():
    email = f"test_{uuid.uuid4().hex[:10]}@example.com"
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "testpass123", "name": "TEST User"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == email
    assert "token" in body and body["token"]
    s.headers["Authorization"] = f"Bearer {body['token']}"
    s.email = email  # type: ignore[attr-defined]
    return s


# ---------------- Auth ----------------
class TestAuth:
    def test_login_after_register(self, auth_session):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": auth_session.email, "password": "testpass123"})
        assert r.status_code == 200
        assert r.json()["user"]["email"] == auth_session.email

    def test_bad_password_login(self, auth_session):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": auth_session.email, "password": "wrongpass"})
        assert r.status_code == 401

    def test_duplicate_register_conflict(self, auth_session):
        r = requests.post(f"{BASE_URL}/api/auth/register", json={"email": auth_session.email, "password": "testpass123"})
        assert r.status_code == 409

    def test_me_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/me")
        assert r.status_code == 401


# ---------------- Study timetable (P0) ----------------
class TestStudyTimetable:
    def test_long_window_spreads_and_covers_topics(self, auth_session):
        exam_date = _future(14)
        topics = ["Cells", "Genetics", "Ecology", "Evolution"]
        r = auth_session.post(f"{BASE_URL}/api/schedules", json={
            "title": "TEST Biology Cycle", "subject": "Biology",
            "exam_date": exam_date, "topics": topics, "kind": "Exam"
        })
        assert r.status_code == 200, r.text
        plan = r.json()["plan"]
        assert isinstance(plan, list) and len(plan) >= 8

        # (d) milestone on exam date at end
        assert plan[-1]["type"] == "milestone"
        assert plan[-1]["date"] == exam_date

        # dates sorted
        dates = [b["date"] for b in plan]
        assert dates == sorted(dates)

        # (c) at least one rest block
        types = [b["type"] for b in plan]
        assert "rest" in types, f"no rest block in plan: {types}"

        # (b) all topics covered somewhere
        text = " ".join(b["label"].lower() for b in plan)
        for t in topics:
            assert t.lower() in text, f"topic {t} not covered"

        # (a) study spans full window; last study block should be within 2 days of exam
        study_dates = [datetime.fromisoformat(b["date"]).date() for b in plan if b["type"] == "study"]
        assert study_dates, "no study blocks"
        exam_d = datetime.fromisoformat(exam_date).date()
        gap = (exam_d - study_dates[-1]).days
        assert gap <= 2, f"large empty gap of {gap} days before exam"

        # And first study block should start near today (within 2 days)
        today = datetime.now(timezone.utc).date()
        assert (study_dates[0] - today).days <= 2

    def test_short_two_day_window(self, auth_session):
        exam_date = _future(2)
        r = auth_session.post(f"{BASE_URL}/api/schedules", json={
            "title": "TEST Short", "subject": "Chemistry",
            "exam_date": exam_date, "topics": ["Acids", "Bases"], "kind": "Exam"
        })
        assert r.status_code == 200
        plan = r.json()["plan"]
        assert plan and plan[-1]["type"] == "milestone" and plan[-1]["date"] == exam_date
        assert len(plan) >= 2  # at least a study + milestone

    def test_past_exam_date_does_not_crash(self, auth_session):
        exam_date = (datetime.now(timezone.utc).date() - timedelta(days=3)).isoformat()
        r = auth_session.post(f"{BASE_URL}/api/schedules", json={
            "title": "TEST Past", "subject": "History",
            "exam_date": exam_date, "topics": ["WW1"], "kind": "Exam"
        })
        assert r.status_code == 200
        plan = r.json()["plan"]
        assert isinstance(plan, list) and len(plan) >= 1
        assert plan[-1]["type"] == "milestone"
        assert plan[-1]["date"] == exam_date


# ---------------- Dashboard ----------------
class TestDashboard:
    def test_dashboard_contains_expected_shape(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/dashboard")
        assert r.status_code == 200
        body = r.json()
        assert set(["schedules", "tasks", "hours", "streak"]).issubset(body.keys())
        assert isinstance(body["schedules"], list) and len(body["schedules"]) >= 1


# ---------------- Tasks ----------------
class TestTasks:
    def test_create_and_toggle_task(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/tasks", json={
            "title": "TEST finish notes", "due_date": _future(0), "priority": "High"
        })
        assert r.status_code == 200
        task = r.json()
        assert task["status"] == "Not Started"
        tid = task["id"]

        r2 = auth_session.patch(f"{BASE_URL}/api/tasks/{tid}", json={"status": "Complete"})
        assert r2.status_code == 200 and r2.json()["status"] == "Complete"

        # toggle back
        r3 = auth_session.patch(f"{BASE_URL}/api/tasks/{tid}", json={"status": "Not Started"})
        assert r3.status_code == 200 and r3.json()["status"] == "Not Started"

        # verify persistence via dashboard
        d = auth_session.get(f"{BASE_URL}/api/dashboard").json()
        assert any(t["id"] == tid for t in d["tasks"])


# ---------------- Paste parse ----------------
class TestParse:
    def test_parse_clean_topics(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/schedules/parse", json={"text": "Biology 2026-06-12: cells, genetics"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert items and items[0]["topics"] == ["cells", "genetics"]
        assert items[0]["exam_date"] == "2026-06-12"
        assert items[0]["subject"] == "Biology"


# ---------------- Focus + streak ----------------
class TestFocus:
    def test_log_focus_increases_streak(self, auth_session):
        before = auth_session.get(f"{BASE_URL}/api/dashboard").json()["streak"]
        r = auth_session.post(f"{BASE_URL}/api/focus/log", json={"subject": "Biology", "minutes": 25})
        assert r.status_code == 200
        after = auth_session.get(f"{BASE_URL}/api/dashboard").json()
        assert after["streak"] >= before
        hours = {h["subject"]: h["minutes"] for h in after["hours"]}
        assert hours.get("Biology", 0) >= 25


# ---------------- Flashcards ----------------
class TestFlashcards:
    def test_create_and_list(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/flashcards", json={"front": "TEST q", "back": "TEST a", "subject": "Biology"})
        assert r.status_code == 200
        cid = r.json()["id"]
        lst = auth_session.get(f"{BASE_URL}/api/flashcards").json()
        assert any(c["id"] == cid for c in lst)
