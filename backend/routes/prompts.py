import json
from fastapi import APIRouter
from data.prompts import PROMPT_LIBRARY
from databases.database import get_db
from models.entry_models import PersonalizedPromptRequest
from ai_service import generate_personalized_prompt

router = APIRouter(prefix="/prompts", tags=["Prompts"])


@router.get("/")
def get_all_prompt_categories():
    return list(PROMPT_LIBRARY.keys())


@router.get("/{emotion}")
def get_prompts_for_emotion(emotion: str):
    return PROMPT_LIBRARY.get(emotion, [])


@router.post("/personalized")
def get_personalized_prompt(body: PersonalizedPromptRequest):
    """
    Generate a single journaling prompt tailored to the user's recent entries + preferences.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Recent entries
    cursor.execute(
        "SELECT content, created_at FROM journal_entries WHERE user_id = ? ORDER BY created_at DESC LIMIT 3",
        (body.user_id,),
    )
    raw_entries = [{"content": r["content"], "created_at": r["created_at"]} for r in cursor.fetchall()]

    # User preferences
    cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (body.user_id,))
    prefs_row = cursor.fetchone()
    prefs = dict(prefs_row) if prefs_row else None

    conn.close()

    try:
        prompt_text = generate_personalized_prompt(raw_entries, prefs)
    except Exception:
        prompt_text = "What's one thing that's been quietly on your mind lately?"

    return {"prompt": prompt_text}
