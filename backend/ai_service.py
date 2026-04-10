# backend/ai_service.py
import json
from models.entry_models import PromptEntryCreate
from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_BASE_SYSTEM = """You are a supportive reflection assistant for a personal journaling app.
Read the user's journal entry and respond with:
1. A paraphrase of the main emotion or situation in 1-2 sentences. Start with "It sounds like..." or "It seems like..."
2. One possible pattern or contributing factor. Start with "One possible factor..." or "I notice..."
3. One gentle clarifying question that invites reflection. Keep it open-ended and non-directive.

Use calm, warm, neutral language. Validate feelings without diagnosing.
Do NOT provide therapy, medical advice, or prescriptive instructions.
Keep the total response under 130 words.
"""


# ─────────────────────────────────────
# Preference context builder
# ─────────────────────────────────────
def build_preference_context(prefs: dict | None) -> str:
    """Return a system-prompt snippet that personalises tone and avoids trigger words."""
    if not prefs:
        return ""

    parts: list[str] = []

    tone = prefs.get("tone_preference", "gentle")
    if tone == "direct":
        parts.append(
            "Tone: be direct and concise. Skip long gentle lead-ins. "
            "Get to the point while remaining respectful."
        )
    elif tone == "balanced":
        parts.append(
            "Tone: warm but clear — supportive without being overly soft."
        )
    # gentle is the default; no extra instruction needed

    raw_words = prefs.get("trigger_words") or "[]"
    try:
        trigger_words: list[str] = json.loads(raw_words) if isinstance(raw_words, str) else raw_words
    except Exception:
        trigger_words = []
    if trigger_words:
        words = ", ".join(f'"{w}"' for w in trigger_words)
        parts.append(f"Avoid using these words or concepts: {words}. Find alternative framings when relevant.")

    values = (prefs.get("user_values") or "").strip()
    if values:
        parts.append(f"The user values: {values}. Where naturally relevant, acknowledge alignment with these.")

    return " ".join(parts)


# ─────────────────────────────────────
# Core reflection (with optional CBT template + hints)
# ─────────────────────────────────────
def generate_reflection(
    journal_text: str,
    template: dict | None = None,
    combined_hint: str = "",
) -> str:
    system = _BASE_SYSTEM

    if template:
        system += f"""
Additionally, use this reflection approach ({template['technique']}):
{template['instruction']}

Add this disclaimer on its own line at the end:
_{template['disclaimer']}_
"""

    if combined_hint:
        system += f"\n{combined_hint}"

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": journal_text},
        ],
        temperature=0.7,
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


# ─────────────────────────────────────
# Emotion tag suggestion
# ─────────────────────────────────────
def suggest_emotions(journal_text: str) -> list:
    prompt = (
        f"Read the following journal entry and suggest 3-5 emotion tags as single words or short phrases.\n"
        f"Journal entry:\n{journal_text}\n\n"
        f"Output ONLY a comma-separated list of emotions (e.g. \"anxiety, overwhelm, self-doubt\").\nNo other text."
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=50,
    )
    tags_text = response.choices[0].message.content.strip()
    return [t.strip().lower() for t in tags_text.split(",") if t.strip()]


# ─────────────────────────────────────
# Prompt-based entry response
# ─────────────────────────────────────
def generate_ai_response(entry: PromptEntryCreate, prefs: dict | None = None) -> str:
    pref_hint = build_preference_context(prefs)
    system = (
        "You are a mental wellness journaling companion.\n"
        "The user has responded to a guided reflection prompt.\n"
        "Reflect back what they shared, validate their experience, and ask ONE gentle follow-up question.\n"
        "Avoid giving advice unless explicitly asked. Keep tone calm, warm, and human.\n"
        "Under 100 words total."
    )
    if pref_hint:
        system += f"\n{pref_hint}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Prompt ID: {entry.prompt_id}\nEmotion: {entry.emotion}\nResponse:\n{entry.content}"},
        ],
        temperature=0.7,
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()


# ─────────────────────────────────────
# Dynamic follow-up conversation
# ─────────────────────────────────────
def generate_followup(entry_content: str, conversation_history: list, turn: int) -> dict:
    if turn == 1:
        system = """You are a supportive journaling companion in an expanded reflection.

Turn 1 rules:
- Write 1-2 sentences reflecting the user's journal entry (use "It sounds like..." or "I notice...")
- Ask ONE specific clarifying question with 2-4 short answer options
- End your response with: OPTIONS: <choice 1> | <choice 2> | <choice 3>
  Example: OPTIONS: Myself | Others | External circumstances | All of these
- Whole response under 80 words. Do NOT give advice or diagnose."""
    elif turn == 2:
        system = """You are a supportive journaling companion, turn 2 of 3.
The user responded to your question. Reflect on their answer and ask ONE deeper follow-up.
2-3 sentences max. No constrained options. Stay curious, warm, non-directive."""
    else:
        system = """You are a supportive journaling companion in the final turn.
Summarise what you heard in 1-2 sentences, offer one gentle closing observation, and end with a brief affirmation.
Under 80 words."""

    messages = [{"role": "system", "content": system}]
    messages.append({"role": "user", "content": f"Journal entry: {entry_content}"})
    messages.extend(conversation_history)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_tokens=160,
    )
    text = response.choices[0].message.content.strip()

    options: list[str] = []
    if turn == 1 and "OPTIONS:" in text:
        parts = text.split("OPTIONS:", 1)
        text = parts[0].strip()
        options = [o.strip() for o in parts[1].strip().split("|") if o.strip()]

    return {"text": text, "options": options, "turn": turn, "is_final": turn >= 3}


# ─────────────────────────────────────
# Pattern / insights analysis
# ─────────────────────────────────────
def generate_insights(entries: list) -> dict:
    if len(entries) < 2:
        return {
            "emotional_arc": None,
            "recurring_triggers": [],
            "weekly_patterns": None,
            "insights": ["Keep journaling — patterns emerge over time."],
        }

    entries_text = "\n\n".join([
        f"[{e['created_at'][:10]}, Energy: {e.get('energy_level') or '?'}/5]\n"
        f"{e['content'][:250]}\n"
        f"Tags: {', '.join(t['tag'] for t in e.get('tags', []))}"
        for e in entries[:10]
    ])

    system = """You are a pattern analysis assistant for a journaling app.
Analyse these recent journal entries and identify 2-3 gentle, specific insights.

Return ONLY a valid JSON object:
{
  "emotional_arc": "one sentence about overall trend, or null",
  "recurring_triggers": ["situation that recurs", "another one"],
  "weekly_patterns": "one sentence about time/context patterns, or null",
  "insights": [
    "Insight starting with 'It looks like...' or 'You tend to...'",
    "Second insight",
    "Optional third insight"
  ]
}
Keep insights non-judgmental and observational."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": entries_text},
        ],
        temperature=0.4,
        max_tokens=400,
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {
            "emotional_arc": None,
            "recurring_triggers": [],
            "weekly_patterns": None,
            "insights": ["Unable to analyse patterns at this time."],
        }


# ─────────────────────────────────────
# Personalized prompt generator
# ─────────────────────────────────────
def generate_personalized_prompt(recent_entries: list, prefs: dict | None) -> str:
    """
    Generate a single, tailored journaling prompt based on recent entries + user preferences.
    """
    entries_summary = " | ".join([e["content"][:120] for e in recent_entries[:3]]) if recent_entries else "No entries yet."

    goals = (prefs or {}).get("goals") or ""
    values = (prefs or {}).get("user_values") or ""
    tone = (prefs or {}).get("tone_preference", "gentle")

    tone_instruction = {
        "direct": "Keep the prompt direct and focused, no fluff.",
        "balanced": "Keep the prompt warm but clear.",
        "gentle": "Keep the prompt gentle, open, and low-pressure.",
    }.get(tone, "")

    system = f"""You are a journaling coach. Write ONE thoughtful journaling prompt for this user.
{tone_instruction}
Make it feel personally relevant given their recent writing and preferences.
Output ONLY the prompt sentence — no preamble, no explanation."""

    user_context = f"Recent entries: {entries_summary}"
    if goals:
        user_context += f"\nUser's goals: {goals}"
    if values:
        user_context += f"\nUser's values: {values}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_context},
        ],
        temperature=0.8,
        max_tokens=80,
    )
    return response.choices[0].message.content.strip().strip('"')


# ─────────────────────────────────────
# Micro-task suggestion
# ─────────────────────────────────────
_ENERGY_CONTEXT = {
    1: "The user is at very low energy (1/5). Suggest something under 2 minutes, almost no effort.",
    2: "The user is at low energy (2/5). Suggest something gentle, under 5 minutes.",
    3: "The user is at moderate energy (3/5). Suggest something taking 5–10 minutes.",
    4: "The user is at good energy (4/5). Suggest something slightly more involved but still small.",
    5: "The user is at high energy (5/5). Suggest something meaningful they might want to do.",
}


def suggest_micro_task(reflection_text: str, energy_level: int | None) -> str:
    energy = max(1, min(5, energy_level or 3))
    system = (
        f"You are a mental wellness companion.\n"
        f"Based on this reflection, suggest ONE tiny, concrete, kind action.\n"
        f"{_ENERGY_CONTEXT[energy]}\n"
        f"One sentence only. Frame with agency: 'If you feel up to it...' or 'One small step could be...'\n"
        f"Relate it to themes in the reflection. Do NOT prescribe or demand."
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Reflection: {reflection_text}"},
        ],
        temperature=0.7,
        max_tokens=80,
    )
    return response.choices[0].message.content.strip()


# ─────────────────────────────────────
# Check-in question
# ─────────────────────────────────────
def generate_checkin_question(recent_entries: list) -> str:
    if not recent_entries:
        return "Welcome back. How are you feeling today compared to the last time you wrote?"

    entries_text = "\n\n---\n\n".join([
        f"Entry ({e['created_at'][:10]}): {e['content'][:300]}"
        for e in recent_entries[:3]
    ])
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a caring journaling companion checking in. "
                    "Based on recent entries, write ONE warm, gentle check-in question (1-2 sentences). "
                    "Briefly reference something specific they mentioned, then ask how things are now. "
                    "Conversational, non-clinical. No advice."
                ),
            },
            {"role": "user", "content": f"Recent entries:\n{entries_text}"},
        ],
        temperature=0.7,
        max_tokens=80,
    )
    return response.choices[0].message.content.strip()


# ─────────────────────────────────────
# Pattern detection (lightweight)
# ─────────────────────────────────────
def detect_patterns(recent_entries: list) -> str | None:
    if len(recent_entries) < 3:
        return None

    tag_counts: dict[str, int] = {}
    for entry in recent_entries:
        seen: set[str] = set()
        for t in entry.get("tags", []):
            tag = t["tag"].lower()
            if tag != "check-in" and tag not in seen:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                seen.add(tag)

    repeated = sorted(
        [(tag, count) for tag, count in tag_counts.items() if count >= 3],
        key=lambda x: -x[1],
    )
    total = min(len(recent_entries), 7)

    if repeated:
        top_tag, count = repeated[0]
        return f"You've mentioned \"{top_tag}\" in {count} of your last {total} entries."

    entries_text = " | ".join([e["content"][:120] for e in recent_entries[:7]])
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "Look at these recent journal excerpts. If ONE clear recurring theme exists, "
                    "write one short sentence like: 'You've mentioned feeling [X] in several recent entries.' "
                    "If no clear pattern, respond with exactly: none"
                ),
            },
            {"role": "user", "content": entries_text},
        ],
        temperature=0.3,
        max_tokens=60,
    )
    result = response.choices[0].message.content.strip()
    return None if result.lower().startswith("none") else result


# ─────────────────────────────────────
# Feedback hint builder
# ─────────────────────────────────────
def build_feedback_hint(feedbacks: list[str]) -> str:
    if not feedbacks:
        return ""
    not_quite = feedbacks.count("not_quite") + feedbacks.count("unhelpful")
    helpful = feedbacks.count("helpful")
    if not_quite >= 2 and not_quite > helpful:
        return (
            "Note: This user has recently found reflections not quite right. "
            "Be more specific, concrete, and directly tied to what they wrote. Avoid generic validation."
        )
    if helpful >= 3 and helpful > not_quite:
        return "Note: This user responds well to the current style. Continue with warmth and specificity."
    return ""
