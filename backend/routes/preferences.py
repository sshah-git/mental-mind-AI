import json
from fastapi import APIRouter
from databases.database import get_db
from models.entry_models import PreferencesUpdate, PreferencesOut

router = APIRouter(prefix="/preferences", tags=["Preferences"])


def _row_to_out(row, user_id: str) -> PreferencesOut:
    if not row:
        return PreferencesOut(user_id=user_id)

    try:
        trigger_words = json.loads(row["trigger_words"] or "[]")
    except Exception:
        trigger_words = []

    return PreferencesOut(
        user_id=row["user_id"],
        tone_preference=row["tone_preference"] or "gentle",
        trigger_words=trigger_words,
        user_values=row["user_values"],
        goals=row["goals"],
        goals_for_journaling=row["goals_for_journaling"],
        reminder_enabled=bool(row["reminder_enabled"]),
        reminder_time=row["reminder_time"],
        onboarding_complete=bool(row["onboarding_complete"]),
    )


@router.get("/{user_id}", response_model=PreferencesOut)
def get_preferences(user_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_out(row, user_id)


@router.put("/{user_id}", response_model=PreferencesOut)
def update_preferences(user_id: str, body: PreferencesUpdate):
    conn = get_db()
    cursor = conn.cursor()

    # Fetch existing row (for merge)
    cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
    existing = cursor.fetchone()

    if not existing:
        # Insert with defaults then apply patch
        cursor.execute(
            "INSERT INTO user_preferences (user_id) VALUES (?)",
            (user_id,),
        )
        cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()

    # Build update dict — only patch provided fields
    updates: dict = {}

    if body.tone_preference is not None:
        updates["tone_preference"] = body.tone_preference
    if body.trigger_words is not None:
        updates["trigger_words"] = json.dumps(body.trigger_words)
    if body.user_values is not None:
        updates["user_values"] = body.user_values
    if body.goals is not None:
        updates["goals"] = body.goals
    if body.goals_for_journaling is not None:
        updates["goals_for_journaling"] = body.goals_for_journaling
    if body.reminder_enabled is not None:
        updates["reminder_enabled"] = int(body.reminder_enabled)
    if body.reminder_time is not None:
        updates["reminder_time"] = body.reminder_time
    if body.onboarding_complete is not None:
        updates["onboarding_complete"] = int(body.onboarding_complete)

    if updates:
        updates["updated_at"] = "CURRENT_TIMESTAMP"
        set_clause = ", ".join(f"{k} = ?" for k in updates if k != "updated_at")
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        values = [v for k, v in updates.items() if k != "updated_at"]
        values.append(user_id)
        cursor.execute(
            f"UPDATE user_preferences SET {set_clause} WHERE user_id = ?",
            values,
        )

    conn.commit()
    cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_out(row, user_id)
