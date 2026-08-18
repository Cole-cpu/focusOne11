"""Vantage AI (Tutor) backend tests.

Coverage:
- POST /api/ai/chat: Socratic behaviour on homework question, concept question, no-LaTeX
- GET /api/ai/messages: persistence (user + assistant chronological)
- DELETE /api/ai/messages: clears
- Personalisation & integrity: real exam data referenced, no fabricated stats
- GET/PUT /api/profile
"""
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")


def _future(days: int) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


@pytest.fixture(scope="module")
def session():
    email = f"ai_{uuid.uuid4().hex[:10]}@example.com"
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "password": "secret123", "name": "TEST AI"})
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    s.email = email  # type: ignore[attr-defined]
    # clear any existing conversation for a clean slate
    s.delete(f"{BASE_URL}/api/ai/messages")
    return s


LATEX_PATTERNS = [
    re.compile(r"\$\$"),
    re.compile(r"(?<!\\)\$[^$\n]{1,50}\$"),
    re.compile(r"\\frac\{"),
    re.compile(r"\\text\{"),
    re.compile(r"\\begin\{"),
]


def _has_latex(text: str) -> bool:
    return any(p.search(text or "") for p in LATEX_PATTERNS)


class TestProfile:
    def test_get_empty_profile(self, session):
        r = session.get(f"{BASE_URL}/api/profile")
        assert r.status_code == 200
        body = r.json()
        assert "user_id" in body

    def test_put_and_get_profile(self, session):
        r = session.put(f"{BASE_URL}/api/profile",
                        json={"grade": "10", "preferred_style": "visual"})
        assert r.status_code == 200, r.text
        assert r.json().get("grade") == "10"
        assert r.json().get("preferred_style") == "visual"
        # verify persisted
        r2 = session.get(f"{BASE_URL}/api/profile")
        assert r2.status_code == 200
        assert r2.json().get("grade") == "10"
        assert r2.json().get("preferred_style") == "visual"


class TestAIChat:
    def test_socratic_homework_no_direct_answer(self, session):
        # Ask a homework-style question
        r = session.post(f"{BASE_URL}/api/ai/chat",
                         json={"message": "What is the answer to 3x + 5 = 20?",
                               "grade": "10", "subject": "Math", "topic": "Linear equations"},
                         timeout=90)
        assert r.status_code == 200, r.text
        reply = r.json().get("reply", "")
        assert reply and isinstance(reply, str)
        # Should NOT give an immediate final answer like "x = 5" up front
        # Accept "x = 5" appearing after a hint/leading question; verify Socratic signal:
        lower = reply.lower()
        socratic_signals = ["?", "hint", "try", "first", "what", "step", "isolate", "start"]
        assert any(s in lower for s in socratic_signals), \
            f"Reply lacks any Socratic guidance markers: {reply!r}"
        # Ideally the very first line does not just state x=5
        first_120 = reply.strip()[:120].lower()
        assert not re.match(r"^\s*x\s*=\s*5\b", first_120), \
            f"Direct answer given immediately: {reply!r}"
        # No LaTeX / $$ / \frac per persona
        assert not _has_latex(reply), f"LaTeX/$$/backslash markup leaked: {reply!r}"

    def test_concept_question_structured(self, session):
        r = session.post(f"{BASE_URL}/api/ai/chat",
                         json={"message": "Explain Newton's second law.",
                               "grade": "10", "subject": "Physics", "topic": "Newton's laws"},
                         timeout=90)
        assert r.status_code == 200, r.text
        reply = r.json().get("reply", "")
        assert reply
        lower = reply.lower()
        # Concept reply should reference F=ma / force / mass / acceleration
        assert ("force" in lower and ("mass" in lower or "acceleration" in lower)) or \
               "f = m" in lower.replace("*", "") or "f=ma" in lower.replace(" ", ""), \
               f"Concept reply missing Newton content: {reply!r}"
        assert not _has_latex(reply), f"LaTeX leaked in concept reply: {reply!r}"


class TestMessagePersistence:
    def test_messages_stored_chronologically(self, session):
        r = session.get(f"{BASE_URL}/api/ai/messages")
        assert r.status_code == 200
        msgs = r.json().get("messages", [])
        # After previous two chats there should be >= 4 messages
        assert len(msgs) >= 4, f"expected >=4 msgs, got {len(msgs)}"
        roles = [m["role"] for m in msgs]
        # Must contain both user and assistant
        assert "user" in roles and "assistant" in roles
        # Chronological (non-decreasing created_at)
        times = [m["created_at"] for m in msgs]
        assert times == sorted(times), "messages not chronological"
        # Alternating starting with user
        assert msgs[0]["role"] == "user"

    def test_delete_messages_clears(self, session):
        r = session.delete(f"{BASE_URL}/api/ai/messages")
        assert r.status_code == 200
        assert r.json().get("cleared") is True
        r2 = session.get(f"{BASE_URL}/api/ai/messages")
        assert r2.status_code == 200
        assert r2.json().get("messages") == []


class TestPersonalisation:
    def test_ai_uses_real_exam_data(self, session):
        # Seed: create a schedule (exam) + a task
        exam_date = _future(10)
        r_sched = session.post(f"{BASE_URL}/api/schedules", json={
            "title": "TEST Biology Midterm",
            "subject": "Biology",
            "exam_date": exam_date,
            "topics": ["Photosynthesis", "Cell respiration"],
            "kind": "Exam",
        })
        assert r_sched.status_code == 200, r_sched.text
        r_task = session.post(f"{BASE_URL}/api/tasks", json={
            "title": "TEST review chapter 4",
            "due_date": _future(2),
            "priority": "High",
            "subject": "Biology",
        })
        assert r_task.status_code == 200

        # Ask Vantage for focus advice
        r = session.post(f"{BASE_URL}/api/ai/chat",
                         json={"message": "What should I focus on for my upcoming exams?",
                               "grade": "10"},
                         timeout=90)
        assert r.status_code == 200, r.text
        reply = r.json().get("reply", "")
        assert reply
        lower = reply.lower()
        # Must reference the real subject/topic we seeded
        assert "biology" in lower, f"Real subject not referenced: {reply!r}"
        assert ("photosynthesis" in lower) or ("cell respiration" in lower) or ("respiration" in lower), \
            f"Real topics not referenced: {reply!r}"
        # Should not fabricate fake statistics (look for suspicious made-up percentages/hours the app never provided)
        # No focus_logs were logged for this user -> reply must not claim study hours
        assert not re.search(r"\b\d+\s*(hours?|hrs?)\s+(spent|of study|studied)", lower), \
            f"Suspicious fabricated stat in reply: {reply!r}"
        assert not _has_latex(reply)


class TestAuthRequired:
    def test_chat_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/ai/chat", json={"message": "hi"})
        assert r.status_code == 401

    def test_messages_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/ai/messages")
        assert r.status_code == 401
