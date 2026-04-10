# mentalmind

A private, AI-assisted journaling app designed for personal reflection. Write freely, track your emotional patterns, and receive thoughtful AI responses — all in a clean, distraction-free interface.

> **This is a personal reflection tool, not a medical service.

---

## Features

### Free tier
- Unlimited journal entries (free-write, guided prompts, or mood check-ins)
- AI reflections after every entry (powered by GPT)
- Emotion & energy tracking
- CBT-informed micro-tasks suggested inline
- Guided prompts for difficult moments
- Multi-turn AI follow-up conversations
- Full entry history with search and tag filters
- Personalization: tone preferences, trigger words, personal values

### Premium tier
- Weekly insights & pattern detection
- Streak tracking with motivational messages
- Weekly PDF summary reports
- Clinician-ready PDF exports
- ICS calendar blocks for journaling sessions
- Email/push reminders (configurable time)

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13 · FastAPI · SQLite |
| AI | OpenAI API (gpt-3.5-turbo / gpt-4o-mini) |
| Auth | JWT (python-jose) · bcrypt (passlib) |
| PDF | fpdf2 |
| Frontend | Vanilla JS · HTML · CSS (no framework) |
| Font | Inter (Google Fonts) |
| PWA | Service worker · Web app manifest |

---

## Project structure

```
mental-mind-AI/
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── auth_utils.py             # JWT helpers, get_current_user, require_premium
│   ├── ai_service.py             # OpenAI calls: reflections, insights, prompts, follow-up
│   ├── databases/
│   │   └── database.py           # SQLite schema + migrations
│   ├── routes/
│   │   ├── auth.py               # /auth/signup, /auth/login, /auth/me, /auth/upgrade
│   │   ├── entries.py            # /entries CRUD, /entries/prompt, /entries/checkin
│   │   ├── reflections.py        # /reflections/{id}/feedback, /followup
│   │   ├── insights.py           # /insights/{user_id} (premium)
│   │   ├── patterns.py           # /patterns/{user_id}
│   │   ├── tasks.py              # /tasks CRUD
│   │   ├── prompts.py            # /prompts/*
│   │   ├── preferences.py        # /preferences/{user_id} GET/PUT
│   │   ├── streaks.py            # /streaks/{user_id} (premium)
│   │   ├── checkin.py            # /checkin/{user_id}
│   │   └── reports.py            # /reports/weekly, /reports/clinician, /reports/calendar-block (premium)
│   └── data/
│       ├── prompts.py            # 17 built-in guided prompts across 7 categories
│       └── cbt_templates.py      # CBT technique library with keyword matching
└── frontend/
    ├── index.html                # Main SPA shell (journal, history, insights, tasks, settings)
    ├── style.css                 # Design system — light + dark mode via CSS custom properties
    ├── script.js                 # All client-side logic: routing, API calls, theme, toasts
    ├── auth.html                 # Login / sign-up page
    ├── auth.css                  # Auth page styles
    ├── auth.js                   # Auth form handlers, JWT storage, redirect guard
    ├── manifest.json             # PWA manifest
    └── sw.js                     # Service worker with offline queue (IndexedDB)
```

---

## Setup

### Prerequisites
- Python 3.11+
- An [OpenAI API key](https://platform.openai.com/api-keys)

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/mental-mind-AI.git
cd mental-mind-AI
```

### 2. Create a virtual environment and install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**`requirements.txt` should include:**
```
fastapi
uvicorn[standard]
python-jose[cryptography]
passlib[bcrypt]
openai
fpdf2
python-multipart
```

### 3. Set environment variables

Create a `.env` file inside `backend/`:

```env
OPENAI_API_KEY=sk-...
SECRET_KEY=your-jwt-secret-here
```

> `SECRET_KEY` can be any long random string. Generate one with:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

### 4. Run the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### 5. Open the frontend

The frontend is plain HTML/CSS/JS — no build step required.

Open `frontend/index.html` directly in your browser, or serve it with any static file server:

```bash
# Python built-in server
cd frontend
python -m http.server 3000
# then open http://localhost:3000/auth.html
```

> Make sure the backend is running on port 8000 before using the app. The frontend fetches from `http://localhost:8000` by default.

---

## API reference

### Auth

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | — | Create a new account |
| POST | `/auth/login` | — | Sign in, returns JWT |
| GET | `/auth/me` | Bearer | Get current user info |
| POST | `/auth/upgrade` | Bearer | Upgrade to premium |
| POST | `/auth/downgrade` | Bearer | Downgrade to free |

### Entries

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/entries` | Bearer | Submit a free-write entry |
| POST | `/entries/prompt` | Bearer | Submit a prompt-based entry |
| POST | `/entries/checkin` | Bearer | Submit a mood check-in |
| GET | `/entries/{user_id}` | Bearer | List all entries for a user |

### Reflections & follow-up

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/reflections/{id}/feedback` | Bearer | Rate an AI reflection |
| POST | `/followup` | Bearer | Continue a multi-turn AI conversation |

### Insights & patterns

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/insights/{user_id}` | Bearer · premium | AI-generated weekly insights |
| GET | `/patterns/{user_id}` | Bearer | Emotion pattern summary |
| GET | `/streaks/{user_id}` | Bearer · premium | Current journaling streak |
| GET | `/checkin/{user_id}` | Bearer | Mood check-in history |

### Tasks

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/tasks/{user_id}` | Bearer | List tasks |
| POST | `/tasks` | Bearer | Create a task |
| PUT | `/tasks/{id}` | Bearer | Update a task |
| DELETE | `/tasks/{id}` | Bearer | Delete a task |

### Prompts

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/prompts` | Bearer | List all built-in prompts |
| GET | `/prompts/random` | Bearer | Get a random prompt |

### Preferences

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/preferences/{user_id}` | Bearer | Get user preferences |
| PUT | `/preferences/{user_id}` | Bearer | Update preferences |

### Reports (premium)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/reports/weekly/{user_id}` | Bearer · premium | Download weekly PDF report |
| GET | `/reports/clinician/{user_id}` | Bearer · premium | Download clinician PDF export |
| POST | `/reports/calendar-block` | Bearer · premium | Download ICS calendar event |

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key |
| `SECRET_KEY` | Yes | JWT signing secret (long random string) |

---

## Dark mode

The app ships with full light, dark, and system-preference theme support. Theme preference is persisted in `localStorage` and applied before the first paint to prevent any flash of unstyled content.

Toggle the theme from the sidebar icon (desktop) or via **Settings → Appearance**.

---

## PWA support

The frontend includes a `manifest.json` and `sw.js` service worker. On supported browsers you can install mentalmind as a home screen app. Journal entries written while offline are queued in IndexedDB and synced automatically when the connection is restored.

---

## Contributing

Pull requests are welcome for bug fixes and accessibility improvements.

1. Fork the repo
2. Create a feature branch (`git checkout -b fix/your-fix`)
3. Commit your changes
4. Open a pull request

---

## License

MIT — do whatever you want, just don't use it as a substitute for professional mental health care.
