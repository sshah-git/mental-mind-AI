from fastapi import APIRouter, Depends, HTTPException
from datetime import date, timedelta, datetime
from databases.database import get_db
from models.entry_models import StreakOut
from auth_utils import require_premium

router = APIRouter(prefix="/streaks", tags=["Streaks"])


def _calculate_streak(date_strings: list[str]) -> dict:
    """
    Given a list of ISO date strings (YYYY-MM-DD), compute:
      - current_streak  (consecutive days ending on today or yesterday)
      - longest_streak  (all-time best run)
      - last_entry      (most recent date)
      - has_entry_today
    """
    if not date_strings:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "last_entry": None,
            "has_entry_today": False,
        }

    dates = sorted({date.fromisoformat(d[:10]) for d in date_strings})
    today = date.today()

    # Longest streak (ascending pass)
    longest = 1
    run = 1
    for i in range(1, len(dates)):
        if dates[i] == dates[i - 1] + timedelta(days=1):
            run += 1
            longest = max(longest, run)
        else:
            run = 1

    # Current streak (descending from today)
    sorted_desc = sorted(dates, reverse=True)
    has_entry_today = sorted_desc[0] == today

    current = 0
    check = today
    for d in sorted_desc:
        if d == check:
            current += 1
            check -= timedelta(days=1)
        elif d < check:
            break  # gap found

    return {
        "current_streak": current,
        "longest_streak": longest,
        "last_entry": sorted_desc[0].isoformat(),
        "has_entry_today": has_entry_today,
    }


def _build_message(streak: dict) -> str:
    c = streak["current_streak"]
    has_today = streak["has_entry_today"]

    if c == 0:
        return "Start your journaling rhythm — write your first entry."
    if c == 1 and not has_today:
        return "You journaled yesterday. Come back today to keep your rhythm going."
    if c == 1:
        return "You journaled today — that counts."
    if not has_today:
        return f"You've written {c} days in a row. Come back today to continue."
    return f"You've written {c} days in a row. Keep going."


@router.get("/{user_id}", response_model=StreakOut)
def get_streak(user_id: str, current_user: dict = Depends(require_premium)):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT created_at FROM journal_entries WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    dates = [row["created_at"] for row in rows]
    data = _calculate_streak(dates)
    data["message"] = _build_message(data)
    return StreakOut(**data)
