import json
from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict, Any


# ─── Shared sub-models ───────────────────────────────────────────
class ReflectionOut(BaseModel):
    reflection_id: str
    reflection_text: str
    user_feedback: Optional[str] = None


class TagOut(BaseModel):
    tag: str
    source: str
    is_private: bool = False


# ─── Journal entries ─────────────────────────────────────────────
class EntryOut(BaseModel):
    entry_id: str
    content: str
    energy_level: Optional[int] = None
    created_at: str
    reflections: List[ReflectionOut] = []
    tags: List[TagOut] = []


class EntryCreate(BaseModel):
    user_id: str
    content: str
    energy_level: Optional[int] = None


class PromptEntryCreate(BaseModel):
    user_id: str
    content: str
    prompt_id: str
    emotion: Optional[str] = None
    energy_level: Optional[int] = None


class CheckinEntryCreate(BaseModel):
    user_id: str
    content: str
    checkin_question: str
    energy_level: Optional[int] = None


# ─── Feedback ────────────────────────────────────────────────────
class FeedbackUpdate(BaseModel):
    feedback: str


# ─── Follow-up conversation ──────────────────────────────────────
class FollowupCreate(BaseModel):
    entry_id: str
    entry_content: str
    conversation_history: List[Dict[str, str]]
    user_message: Optional[str] = None
    turn: int


class FollowupOut(BaseModel):
    text: str
    options: List[str] = []
    turn: int
    is_final: bool


# ─── Patterns & insights ─────────────────────────────────────────
class PatternOut(BaseModel):
    has_pattern: bool
    pattern_message: Optional[str] = None
    top_tags: List[str] = []


class InsightsOut(BaseModel):
    emotional_arc: Optional[str] = None
    recurring_triggers: List[str] = []
    weekly_patterns: Optional[str] = None
    insights: List[str] = []


# ─── Check-in ────────────────────────────────────────────────────
class CheckinOut(BaseModel):
    checkin_question: str
    context_summary: Optional[str] = None


# ─── Micro-tasks ─────────────────────────────────────────────────
class TaskSuggestRequest(BaseModel):
    user_id: str
    reflection_text: str
    energy_level: Optional[int] = None


class TaskCreate(BaseModel):
    user_id: str
    task_text: str
    energy_required: Optional[int] = None


class TaskStatusUpdate(BaseModel):
    status: str


class TaskOut(BaseModel):
    task_id: str
    task_text: str
    energy_required: Optional[int] = None
    status: str
    created_at: str


# ─── Private tags ─────────────────────────────────────────────────
class PrivateTagCreate(BaseModel):
    tag: str


# ─── User preferences ────────────────────────────────────────────
class PreferencesUpdate(BaseModel):
    tone_preference: Optional[str] = None          # 'gentle' | 'balanced' | 'direct'
    trigger_words: Optional[List[str]] = None
    user_values: Optional[str] = None
    goals: Optional[str] = None
    goals_for_journaling: Optional[str] = None
    reminder_enabled: Optional[bool] = None
    reminder_time: Optional[str] = None            # "HH:MM"
    onboarding_complete: Optional[bool] = None


class PreferencesOut(BaseModel):
    user_id: str
    tone_preference: str = "gentle"
    trigger_words: List[str] = []
    user_values: Optional[str] = None
    goals: Optional[str] = None
    goals_for_journaling: Optional[str] = None
    reminder_enabled: bool = False
    reminder_time: Optional[str] = None
    onboarding_complete: bool = False


# ─── Streaks ─────────────────────────────────────────────────────
class StreakOut(BaseModel):
    current_streak: int
    longest_streak: int
    last_entry: Optional[str] = None
    has_entry_today: bool
    message: str


# ─── Reports ─────────────────────────────────────────────────────
class CalendarBlockRequest(BaseModel):
    user_id: str
    duration_hours: int = 2
    label: str = "Rest & Recovery"


# ─── Personalized prompt ─────────────────────────────────────────
class PersonalizedPromptRequest(BaseModel):
    user_id: str
