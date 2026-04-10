"""
Reports — PDF export (weekly summary + clinician export) and calendar ICS generation.
Requires: pip install fpdf2
"""
import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response
from auth_utils import require_premium

from databases.database import get_db
from models.entry_models import CalendarBlockRequest

router = APIRouter(prefix="/reports", tags=["Reports"])

try:
    from fpdf import FPDF
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False


# ─────────────────────────────────────
# PDF base class
# ─────────────────────────────────────
if _PDF_AVAILABLE:
    class _MindPDF(FPDF):
        def __init__(self, subtitle: str = ""):
            super().__init__()
            self._subtitle = subtitle
            self.set_auto_page_break(auto=True, margin=22)
            self.set_margins(20, 20, 20)

        def header(self):
            self.set_font("Helvetica", "B", 15)
            self.set_text_color(50, 100, 80)
            self.cell(0, 8, "mentalmind", ln=True, align="C")
            self.set_font("Helvetica", "", 9)
            self.set_text_color(110, 110, 110)
            self.cell(0, 5, self._subtitle, ln=True, align="C")
            self.cell(0, 5, f"Generated {datetime.now().strftime('%B %d, %Y')}", ln=True, align="C")
            self.set_text_color(0, 0, 0)
            self.ln(5)

        def footer(self):
            self.set_y(-20)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(160, 160, 160)
            self.multi_cell(
                0, 4,
                "This report is for personal reflection only. It is not a clinical document or therapy.\n"
                "In crisis? Call 988 (US), 116 123 (Samaritans UK), or findahelpline.com",
                align="C",
            )
            self.set_text_color(0, 0, 0)

        def section(self, title: str):
            self.ln(4)
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(50, 100, 80)
            self.cell(0, 7, title, ln=True)
            self.set_draw_color(200, 230, 220)
            self.line(self.get_x(), self.get_y(), self.get_x() + 170, self.get_y())
            self.ln(3)
            self.set_text_color(40, 40, 40)

        def body(self, text: str):
            self.set_font("Helvetica", "", 9)
            self.set_text_color(55, 55, 55)
            self.multi_cell(0, 5, text)
            self.ln(2)
            self.set_text_color(40, 40, 40)

        def bullet(self, text: str):
            self.set_font("Helvetica", "", 9)
            self.set_text_color(55, 55, 55)
            self.cell(6, 5, "\u2022", ln=False)
            self.multi_cell(0, 5, text)
            self.set_text_color(40, 40, 40)

        def label(self, text: str):
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(90, 90, 90)
            self.cell(0, 5, text.upper(), ln=True)
            self.set_text_color(40, 40, 40)

        def entry_block(self, date_str: str, content: str, reflection: str, energy: str, tags: list[str]):
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(80, 80, 80)
            meta = date_str
            if energy:
                meta += f"  ·  Energy {energy}/5"
            if tags:
                meta += f"  ·  {', '.join(tags)}"
            self.cell(0, 5, meta, ln=True)

            self.set_font("Helvetica", "", 9)
            self.set_text_color(40, 40, 40)
            self.multi_cell(0, 5, content[:400] + ("…" if len(content) > 400 else ""))

            if reflection:
                self.set_font("Helvetica", "I", 8)
                self.set_text_color(100, 100, 100)
                self.multi_cell(0, 5, reflection[:300] + ("…" if len(reflection) > 300 else ""))

            self.set_text_color(40, 40, 40)
            self.ln(3)


# ─────────────────────────────────────
# Helpers
# ─────────────────────────────────────
def _fetch_entries_for_report(user_id: str, days: int = 7) -> list[dict]:
    conn = get_db()
    cursor = conn.cursor()

    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute(
        """SELECT id, content, energy_level, created_at
           FROM journal_entries
           WHERE user_id = ? AND date(created_at) >= ?
           ORDER BY created_at DESC""",
        (user_id, since),
    )
    rows = cursor.fetchall()

    entries = []
    for row in rows:
        cursor.execute(
            "SELECT * FROM ai_reflections WHERE entry_id = ? ORDER BY created_at ASC LIMIT 1",
            (row["id"],),
        )
        ref = cursor.fetchone()

        cursor.execute("SELECT tag FROM entry_tags WHERE entry_id = ? AND is_private = 0", (row["id"],))
        tags = [t["tag"] for t in cursor.fetchall() if t["tag"] != "check-in"]

        entries.append({
            "content": row["content"].replace("[Check-in] ", ""),
            "energy_level": row["energy_level"],
            "created_at": row["created_at"],
            "reflection": ref["reflection_text"] if ref else "",
            "tags": tags,
        })

    conn.close()
    return entries


def _fetch_patterns_summary(user_id: str) -> list[str]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT pattern_summary FROM detected_patterns
           WHERE user_id = ? AND pattern_type = 'insight'
           ORDER BY last_detected DESC LIMIT 3""",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [r["pattern_summary"] for r in rows]


def _fetch_pending_tasks(user_id: str) -> list[str]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT task_text FROM micro_tasks WHERE user_id = ? AND status = 'pending' LIMIT 3",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [r["task_text"] for r in rows]


# ─────────────────────────────────────
# GET /reports/weekly/{user_id}
# ─────────────────────────────────────
@router.get("/weekly/{user_id}")
def weekly_report(user_id: str, current_user: dict = Depends(require_premium)):
    if not _PDF_AVAILABLE:
        raise HTTPException(status_code=503, detail="PDF not available. Run: pip install fpdf2")

    entries  = _fetch_entries_for_report(user_id, days=7)
    patterns = _fetch_patterns_summary(user_id)
    tasks    = _fetch_pending_tasks(user_id)

    pdf = _MindPDF("Weekly Reflection Report")
    pdf.add_page()

    # Summary stat
    date_range = f"Past 7 days  ·  {len(entries)} {'entry' if len(entries) == 1 else 'entries'}"
    pdf.section("Your Week at a Glance")
    pdf.body(date_range)

    if entries:
        energies = [e["energy_level"] for e in entries if e["energy_level"]]
        if energies:
            avg_energy = sum(energies) / len(energies)
            pdf.body(f"Average energy: {avg_energy:.1f} / 5")

    # Patterns
    if patterns:
        pdf.section("Patterns Noticed")
        for p in patterns:
            pdf.bullet(p)

    # Entries
    pdf.section(f"This Week's Entries ({len(entries)})")
    if entries:
        for e in entries:
            ts = datetime.fromisoformat(e["created_at"]).strftime("%a %b %-d")
            pdf.entry_block(
                ts,
                e["content"],
                e["reflection"],
                str(e["energy_level"]) if e["energy_level"] else "",
                e["tags"],
            )
    else:
        pdf.body("No entries this week yet.")

    # Action plan
    if tasks:
        pdf.section("Your Small Steps")
        for t in tasks:
            pdf.bullet(t)
    else:
        pdf.section("A Gentle Suggestion")
        pdf.body(
            "Try writing for just 5 minutes this week — even a single sentence counts. "
            "Consistency matters more than length."
        )

    buf = io.BytesIO(pdf.output())
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=mentalmind-weekly-report.pdf"},
    )


# ─────────────────────────────────────
# GET /reports/clinician/{user_id}
# ─────────────────────────────────────
@router.get("/clinician/{user_id}")
def clinician_export(user_id: str, days: int = 30, current_user: dict = Depends(require_premium)):
    if not _PDF_AVAILABLE:
        raise HTTPException(status_code=503, detail="PDF not available. Run: pip install fpdf2")

    entries  = _fetch_entries_for_report(user_id, days=days)
    patterns = _fetch_patterns_summary(user_id)

    pdf = _MindPDF("Personal Reflection Export — For Optional Sharing")
    pdf.add_page()

    # Disclaimer banner
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 80, 40)
    pdf.multi_cell(
        0, 5,
        "IMPORTANT: This document was generated by the user for their own use and optional sharing with "
        "a mental health provider. It is not a clinical assessment, diagnosis, or treatment record. "
        "All content is self-reported.",
    )
    pdf.set_text_color(40, 40, 40)
    pdf.ln(4)

    # Summary
    since = (datetime.now() - timedelta(days=days)).strftime("%B %d, %Y")
    pdf.section("Export Summary")
    pdf.body(f"Date range: {since} – {datetime.now().strftime('%B %d, %Y')}")
    pdf.body(f"Total entries included: {len(entries)}")

    if entries:
        energies = [e["energy_level"] for e in entries if e["energy_level"]]
        if energies:
            pdf.body(f"Energy level range: {min(energies)}–{max(energies)} / 5 (avg {sum(energies)/len(energies):.1f})")

    # Patterns
    if patterns:
        pdf.section("Recurring Themes (AI-Detected)")
        pdf.body("The following themes were detected across recent entries by an AI assistant:")
        for p in patterns:
            pdf.bullet(p)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(120, 120, 120)
        pdf.body("Note: AI-detected patterns are observational, not diagnostic.")
        pdf.set_text_color(40, 40, 40)

    # All tag frequency
    all_tags: dict[str, int] = {}
    for e in entries:
        for t in e["tags"]:
            all_tags[t] = all_tags.get(t, 0) + 1
    if all_tags:
        pdf.section("Emotion Tag Frequency")
        sorted_tags = sorted(all_tags.items(), key=lambda x: -x[1])
        for tag, count in sorted_tags[:10]:
            pdf.body(f"{tag}: {count} occurrence{'s' if count != 1 else ''}")

    # Entries
    pdf.section(f"Journal Entries ({len(entries)} total, most recent first)")
    if entries:
        for e in entries:
            ts = datetime.fromisoformat(e["created_at"]).strftime("%B %-d, %Y")
            pdf.entry_block(
                ts,
                e["content"],
                e["reflection"],
                str(e["energy_level"]) if e["energy_level"] else "",
                e["tags"],
            )
    else:
        pdf.body("No entries in this date range.")

    buf = io.BytesIO(pdf.output())
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=mentalmind-clinician-export.pdf"},
    )


# ─────────────────────────────────────
# POST /reports/calendar-block
# ─────────────────────────────────────
@router.post("/calendar-block")
def calendar_block(body: CalendarBlockRequest, current_user: dict = Depends(require_premium)):
    """
    Generate a downloadable .ics calendar file to block recovery time.
    No OAuth required — user imports the file into any calendar app.
    """
    now   = datetime.now(tz=timezone.utc)
    start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    end   = start + timedelta(hours=max(1, min(4, body.duration_hours)))

    fmt = "%Y%m%dT%H%M%SZ"
    uid = str(uuid.uuid4())

    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//mentalmind//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTART:{start.strftime(fmt)}\r\n"
        f"DTEND:{end.strftime(fmt)}\r\n"
        f"SUMMARY:{body.label}\r\n"
        "DESCRIPTION:Blocked based on your mentalmind energy reflection. "
        "Use this time to rest, recharge, or do something kind for yourself.\r\n"
        "STATUS:CONFIRMED\r\n"
        f"DTSTAMP:{now.strftime(fmt)}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="mentalmind-recovery.ics"'},
    )
