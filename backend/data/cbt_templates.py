"""
CBT-inspired self-reflection templates.
Each template maps to a specific evidence-based technique.
These guide the AI's reflection style — they are NOT therapy.
"""

CBT_TEMPLATES: dict[str, dict] = {
    "cognitive_reframe": {
        "id": "cbt_cognitive_reframe",
        "name": "Cognitive Reframing",
        "technique": "Cognitive Restructuring (CBT)",
        "instruction": (
            "After paraphrasing the user's emotion, gently introduce one alternative perspective. "
            "Use: 'One way to look at this differently might be...' "
            "Then ask: 'Does this reframe feel accessible right now, or does it feel too far from where you are?'"
        ),
        "disclaimer": "This is a self-reflection exercise inspired by cognitive behavioral techniques. It is not therapy.",
    },
    "grounding": {
        "id": "cbt_grounding",
        "name": "Grounding",
        "technique": "Mindfulness-Based Grounding",
        "instruction": (
            "After reflecting on the user's experience, help them find present-moment anchors. "
            "Use: 'Before going deeper, it might help to just notice where you are right now.' "
            "Offer: 'What's one thing in your immediate environment you can focus on for a moment?' "
            "Keep the tone slow, unhurried, and gentle."
        ),
        "disclaimer": "This is a grounding self-reflection exercise. It is not therapy.",
    },
    "self_compassion": {
        "id": "cbt_self_compassion",
        "name": "Self-Compassion",
        "technique": "Compassion-Focused (CFT)",
        "instruction": (
            "After reflecting on the user's experience, invite self-compassion. "
            "Ask: 'What would you say to a close friend who felt exactly this way?' "
            "Then gently: 'Is there even a small amount of that same kindness you could offer yourself right now?'"
        ),
        "disclaimer": "This is a self-compassion exercise. It is not therapy.",
    },
    "behavioral_activation": {
        "id": "cbt_behavioral_activation",
        "name": "Behavioral Activation",
        "technique": "Behavioral Activation (CBT)",
        "instruction": (
            "After reflecting on the user's feelings, gently explore whether one small action might help shift their state. "
            "Use: 'Sometimes when we feel this way, even one tiny action can create a small opening.' "
            "Ask: 'Is there something — however small — that might feel like a gentle first step?'"
        ),
        "disclaimer": "This is a self-reflection exercise. It is not therapy.",
    },
    "thought_record": {
        "id": "cbt_thought_record",
        "name": "Thought Record",
        "technique": "Thought Record (CBT)",
        "instruction": (
            "Help the user examine the thought underneath the feeling. "
            "Use: 'It sounds like the thought driving this might be...' "
            "Then: 'How strongly do you believe that thought right now, if 0 is not at all and 10 is completely?' "
            "Follow with: 'What evidence do you have for and against it?'"
        ),
        "disclaimer": "This is a thought-record self-reflection exercise. It is not therapy.",
    },
}


# ─────────────────────────────────────
# Keyword-based template selector
# No extra AI call — deterministic, fast
# ─────────────────────────────────────
_KEYWORD_MAP: dict[str, list[str]] = {
    "cognitive_reframe": [
        "anxiety", "anxious", "worried", "what if", "fear", "afraid",
        "worst case", "catastroph", "panic", "dreading",
    ],
    "grounding": [
        "overwhelmed", "overwhelm", "too much", "scattered",
        "can't focus", "spinning", "flooding",
    ],
    "self_compassion": [
        "failure", "fail", "disappoint", "worthless", "hate myself",
        "not good enough", "burnout", "exhausted", "ashamed", "embarrassed",
    ],
    "behavioral_activation": [
        "stuck", "unmotivated", "can't move", "numb", "nothing matters",
        "pointless", "hopeless", "don't want to", "avoidance", "avoiding",
    ],
    "thought_record": [
        "should", "must", "always", "never", "everyone thinks",
        "nobody cares", "they think", "people think",
    ],
}


def select_cbt_template(text: str) -> dict | None:
    """Return the best-matching CBT template for a journal entry, or None."""
    text_lower = text.lower()
    scores: dict[str, int] = {k: 0 for k in _KEYWORD_MAP}

    for template_key, keywords in _KEYWORD_MAP.items():
        for kw in keywords:
            if kw in text_lower:
                scores[template_key] += 1

    best = max(scores, key=scores.get)
    return CBT_TEMPLATES.get(best) if scores[best] > 0 else None
