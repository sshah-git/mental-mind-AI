import json
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uuid

from routes.prompts     import router as prompt_router
from routes.preferences import router as prefs_router
from routes.streaks     import router as streaks_router
from routes.reports     import router as reports_router
from routes.auth        import router as auth_router

from databases.database  import get_db, init_db
from data.cbt_templates  import select_cbt_template
from auth_utils          import get_current_user, require_premium

from ai_service import (
    generate_reflection,
    suggest_emotions,
    generate_ai_response,
    generate_followup,
    generate_checkin_question,
    generate_insights,
    detect_patterns,
    suggest_micro_task,
    build_feedback_hint,
    build_preference_context,
)
from models.entry_models import (
    EntryOut, EntryCreate, PromptEntryCreate, CheckinEntryCreate,
    FeedbackUpdate, FollowupCreate, FollowupOut,
    PatternOut, InsightsOut, CheckinOut,
    TaskSuggestRequest, TaskCreate, TaskStatusUpdate, TaskOut,
    PrivateTagCreate,
)

app = FastAPI(title="mentalmind API")

for router in [auth_router, prompt_router, prefs_router, streaks_router, reports_router]:
    app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ─────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────

def _fetch_entry_detail(cursor, entry_id: str) -> dict:
    cursor.execute("SELECT * FROM journal_entries WHERE id = ?", (entry_id,))
    entry = cursor.fetchone()
    if not entry:
        return {}
    cursor.execute("SELECT * FROM ai_reflections WHERE entry_id = ? ORDER BY created_at", (entry_id,))
    reflections = cursor.fetchall()
    cursor.execute("SELECT tag, source, is_private FROM entry_tags WHERE entry_id = ?", (entry_id,))
    tags = cursor.fetchall()
    return {
        "entry_id":    entry["id"],
        "content":     entry["content"],
        "energy_level": entry["energy_level"],
        "created_at":  entry["created_at"],
        "reflections": [{"reflection_id": r["id"], "reflection_text": r["reflection_text"], "user_feedback": r["user_feedback"]} for r in reflections],
        "tags":        [{"tag": t["tag"], "source": t["source"], "is_private": bool(t["is_private"])} for t in tags],
    }


def _get_combined_hint(user_id: str, cursor) -> str:
    cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
    prefs_row = cursor.fetchone()
    prefs     = dict(prefs_row) if prefs_row else None

    cursor.execute(
        """SELECT ar.user_feedback FROM ai_reflections ar
           JOIN journal_entries je ON ar.entry_id = je.id
           WHERE je.user_id = ? AND ar.user_feedback IS NOT NULL
           ORDER BY ar.created_at DESC LIMIT 10""",
        (user_id,),
    )
    feedbacks    = [r["user_feedback"] for r in cursor.fetchall()]
    pref_hint    = build_preference_context(prefs)
    feedback_hint = build_feedback_hint(feedbacks)
    return " ".join(filter(None, [pref_hint, feedback_hint]))


def _get_prefs(user_id: str, cursor) -> dict | None:
    cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def _assert_owns(user_id: str, current_user: dict):
    if user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")


# ─────────────────────────────────────
# Entries
# ─────────────────────────────────────

@app.post("/entries")
def create_entry(entry: EntryCreate, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn    = get_db()
    cursor  = conn.cursor()

    entry_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO journal_entries (id, user_id, content, energy_level) VALUES (?,?,?,?)",
        (entry_id, user_id, entry.content, entry.energy_level),
    )

    template    = select_cbt_template(entry.content)
    hint        = _get_combined_hint(user_id, cursor)

    try:
        reflection_text = generate_reflection(entry.content, template, hint)
    except Exception:
        reflection_text = "I wasn't able to generate a reflection right now. Take a moment to sit with what you've written."

    reflection_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO ai_reflections (id, entry_id, reflection_text, template_id) VALUES (?,?,?,?)",
        (reflection_id, entry_id, reflection_text, template["id"] if template else None),
    )

    try:
        ai_tags = suggest_emotions(entry.content)
    except Exception:
        ai_tags = []
    for tag in ai_tags:
        cursor.execute("INSERT INTO entry_tags (entry_id, tag, source) VALUES (?,?,'ai')", (entry_id, tag))

    conn.commit()
    conn.close()
    return {"entry_id": entry_id, "reflection_id": reflection_id, "reflection_text": reflection_text,
            "ai_tags": ai_tags, "template_used": template["name"] if template else None}


@app.post("/entries/checkin")
def create_checkin_entry(entry: CheckinEntryCreate, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn    = get_db()
    cursor  = conn.cursor()

    entry_id     = str(uuid.uuid4())
    full_content = f"[Check-in] {entry.content}"
    cursor.execute("INSERT INTO journal_entries (id, user_id, content, energy_level) VALUES (?,?,?,?)",
                   (entry_id, user_id, full_content, entry.energy_level))

    hint = _get_combined_hint(user_id, cursor)
    try:
        reflection_text = generate_reflection(
            f"Check-in question: {entry.checkin_question}\nUser response: {entry.content}", combined_hint=hint)
    except Exception:
        reflection_text = "Thank you for checking in."

    reflection_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO ai_reflections (id, entry_id, reflection_text) VALUES (?,?,?)",
                   (reflection_id, entry_id, reflection_text))

    try:
        ai_tags = suggest_emotions(entry.content)
    except Exception:
        ai_tags = []
    for tag in ai_tags:
        cursor.execute("INSERT INTO entry_tags (entry_id, tag, source) VALUES (?,?,'ai')", (entry_id, tag))
    cursor.execute("INSERT INTO entry_tags (entry_id, tag, source) VALUES (?,'check-in','user')", (entry_id,))

    conn.commit()
    conn.close()
    return {"entry_id": entry_id, "reflection_id": reflection_id, "reflection_text": reflection_text, "ai_tags": ai_tags}


@app.post("/entries/prompt")
def create_prompt_entry(entry: PromptEntryCreate, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn    = get_db()
    cursor  = conn.cursor()

    entry_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO journal_entries (id, user_id, content, energy_level) VALUES (?,?,?,?)",
                   (entry_id, user_id, entry.content, entry.energy_level))

    prefs = _get_prefs(user_id, cursor)
    try:
        ai_reply = generate_ai_response(entry, prefs)
    except Exception:
        ai_reply = "Thank you for sharing that."

    reflection_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO ai_reflections (id, entry_id, reflection_text) VALUES (?,?,?)",
                   (reflection_id, entry_id, ai_reply))
    if entry.emotion:
        cursor.execute("INSERT INTO entry_tags (entry_id, tag, source) VALUES (?,?,'user')", (entry_id, entry.emotion))

    conn.commit()
    conn.close()
    return {"entry_id": entry_id, "reflection_id": reflection_id, "reflection_text": ai_reply}


@app.get("/entries/{user_id}", response_model=List[EntryOut])
def get_entries(
    user_id: str,
    search:          Optional[str] = Query(default=None),
    tag:             Optional[str] = Query(default=None),
    from_date:       Optional[str] = Query(default=None),
    to_date:         Optional[str] = Query(default=None),
    energy_min:      Optional[int] = Query(default=None),
    energy_max:      Optional[int] = Query(default=None),
    include_private: bool          = Query(default=True),
    current_user:    dict          = Depends(get_current_user),
):
    _assert_owns(user_id, current_user)
    conn   = get_db()
    cursor = conn.cursor()

    q, params = "SELECT * FROM journal_entries WHERE user_id = ?", [user_id]
    if search:      q += " AND content LIKE ?";      params.append(f"%{search}%")
    if from_date:   q += " AND date(created_at) >= ?"; params.append(from_date)
    if to_date:     q += " AND date(created_at) <= ?"; params.append(to_date)
    if energy_min:  q += " AND energy_level >= ?";   params.append(energy_min)
    if energy_max:  q += " AND energy_level <= ?";   params.append(energy_max)
    if tag:
        priv = "" if include_private else " AND is_private = 0"
        q   += f" AND id IN (SELECT entry_id FROM entry_tags WHERE LOWER(tag)=LOWER(?){priv})"
        params.append(tag)
    q += " ORDER BY created_at DESC"

    cursor.execute(q, params)
    result = [_fetch_entry_detail(cursor, e["id"]) for e in cursor.fetchall()]
    conn.close()
    return result


@app.patch("/reflections/{reflection_id}/feedback")
def update_feedback(reflection_id: str, body: FeedbackUpdate, current_user: dict = Depends(get_current_user)):
    if body.feedback not in {"helpful", "not_quite", "unhelpful"}:
        raise HTTPException(400, "Invalid feedback value")
    conn    = get_db()
    cursor  = conn.cursor()
    cursor.execute("UPDATE ai_reflections SET user_feedback = ? WHERE id = ?", (body.feedback, reflection_id))
    if cursor.rowcount == 0:
        conn.close(); raise HTTPException(404, "Reflection not found")
    conn.commit(); conn.close()
    return {"status": "ok"}


@app.post("/followup", response_model=FollowupOut)
def followup(body: FollowupCreate, current_user: dict = Depends(get_current_user)):
    if body.turn > 3:
        raise HTTPException(400, "Maximum 3 follow-up turns")
    history = list(body.conversation_history)
    if body.user_message:
        history.append({"role": "user", "content": body.user_message})
    return FollowupOut(**generate_followup(body.entry_content, history, body.turn))


@app.get("/patterns/{user_id}", response_model=PatternOut)
def get_patterns(user_id: str, current_user: dict = Depends(get_current_user)):
    _assert_owns(user_id, current_user)
    conn    = get_db()
    cursor  = conn.cursor()
    cursor.execute("SELECT id, content, created_at FROM journal_entries WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (user_id,))
    entries = cursor.fetchall()
    if not entries:
        conn.close(); return PatternOut(has_pattern=False)

    enriched = []
    for e in entries:
        cursor.execute("SELECT tag, source FROM entry_tags WHERE entry_id = ?", (e["id"],))
        tags = [{"tag": t["tag"], "source": t["source"]} for t in cursor.fetchall()]
        enriched.append({"content": e["content"], "created_at": e["created_at"], "tags": tags})

    tag_counts: dict[str, int] = {}
    for e in enriched:
        seen: set[str] = set()
        for t in e["tags"]:
            tag = t["tag"].lower()
            if tag != "check-in" and tag not in seen:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1; seen.add(tag)

    top_tags = [t for t, _ in sorted(tag_counts.items(), key=lambda x: -x[1])[:5]]
    conn.close()

    try:    pattern_msg = detect_patterns(enriched)
    except: pattern_msg = None
    return PatternOut(has_pattern=pattern_msg is not None, pattern_message=pattern_msg, top_tags=top_tags)


@app.get("/insights/{user_id}", response_model=InsightsOut)
def get_insights(user_id: str, current_user: dict = Depends(require_premium)):
    _assert_owns(user_id, current_user)
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, content, energy_level, created_at FROM journal_entries WHERE user_id = ? ORDER BY created_at DESC LIMIT 14", (user_id,))
    raw    = cursor.fetchall()
    if not raw:
        conn.close(); return InsightsOut(insights=["Start journaling to see your patterns emerge."])

    enriched = []
    for e in raw:
        cursor.execute("SELECT tag, source FROM entry_tags WHERE entry_id = ?", (e["id"],))
        tags = [{"tag": t["tag"], "source": t["source"]} for t in cursor.fetchall()]
        enriched.append({"content": e["content"], "energy_level": e["energy_level"], "created_at": e["created_at"], "tags": tags})
    conn.close()

    try:
        data = generate_insights(enriched)
        _store_insights(user_id, data)
    except Exception:
        data = {"emotional_arc": None, "recurring_triggers": [], "weekly_patterns": None, "insights": ["Unable to analyse patterns right now."]}
    return InsightsOut(**data)


def _store_insights(user_id: str, data: dict):
    conn   = get_db()
    cursor = conn.cursor()
    for insight in data.get("insights", []):
        cursor.execute("INSERT INTO detected_patterns (id, user_id, pattern_type, pattern_summary) VALUES (?,?,'insight',?)",
                       (str(uuid.uuid4()), user_id, insight))
    conn.commit(); conn.close()


@app.get("/checkin/{user_id}", response_model=CheckinOut)
def get_checkin(user_id: str, current_user: dict = Depends(get_current_user)):
    _assert_owns(user_id, current_user)
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT content, created_at FROM journal_entries WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (user_id,))
    entries = [{"content": e["content"], "created_at": e["created_at"]} for e in cursor.fetchall()]
    conn.close()

    if not entries:
        return CheckinOut(checkin_question="Welcome. How are you feeling today?")
    try:    question = generate_checkin_question(entries)
    except: question = "How are you feeling today compared to the last time you wrote?"
    return CheckinOut(checkin_question=question, context_summary=f"Based on your entries since {entries[0]['created_at'][:10]}")


# ─── Private tags (premium) ───────────────────────────────────────
@app.post("/entries/{entry_id}/tags/private")
def add_private_tag(entry_id: str, body: PrivateTagCreate, current_user: dict = Depends(require_premium)):
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO entry_tags (entry_id, tag, source, is_private) VALUES (?,?,'user',1)", (entry_id, body.tag.lower().strip()))
    conn.commit(); conn.close()
    return {"status": "ok"}


# ─── Micro-tasks ──────────────────────────────────────────────────
@app.post("/tasks/suggest")
def suggest_task(body: TaskSuggestRequest, current_user: dict = Depends(get_current_user)):
    try:    task_text = suggest_micro_task(body.reflection_text, body.energy_level)
    except: task_text = "If you feel up to it: take one slow, intentional breath."
    return {"task_text": task_text}


@app.post("/tasks", response_model=TaskOut)
def save_task(body: TaskCreate, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn    = get_db()
    cursor  = conn.cursor()
    task_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO micro_tasks (id, user_id, task_text, energy_required, status) VALUES (?,?,?,?,'pending')",
                   (task_id, user_id, body.task_text, body.energy_required))
    conn.commit()
    cursor.execute("SELECT * FROM micro_tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone(); conn.close()
    return TaskOut(task_id=row["id"], task_text=row["task_text"], energy_required=row["energy_required"], status=row["status"], created_at=row["created_at"])


@app.get("/tasks/{user_id}", response_model=List[TaskOut])
def get_tasks(user_id: str, status: Optional[str] = Query(default="pending"), current_user: dict = Depends(get_current_user)):
    _assert_owns(user_id, current_user)
    conn    = get_db()
    cursor  = conn.cursor()
    if status == "all":
        cursor.execute("SELECT * FROM micro_tasks WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    else:
        cursor.execute("SELECT * FROM micro_tasks WHERE user_id = ? AND status = ? ORDER BY created_at DESC", (user_id, status))
    rows = cursor.fetchall(); conn.close()
    return [TaskOut(task_id=r["id"], task_text=r["task_text"], energy_required=r["energy_required"], status=r["status"], created_at=r["created_at"]) for r in rows]


@app.patch("/tasks/{task_id}/status")
def update_task_status(task_id: str, body: TaskStatusUpdate, current_user: dict = Depends(get_current_user)):
    if body.status not in {"done", "skipped"}:
        raise HTTPException(400, "status must be 'done' or 'skipped'")
    conn    = get_db()
    cursor  = conn.cursor()
    cursor.execute("UPDATE micro_tasks SET status = ? WHERE id = ?", (body.status, task_id))
    if cursor.rowcount == 0:
        conn.close(); raise HTTPException(404, "Task not found")
    conn.commit(); conn.close()
    return {"status": "ok"}
