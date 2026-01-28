<!-- Copilot instructions for code assistance in this repository -->
# Quick Onboarding for AI coding agents

This file captures the minimal, actionable project knowledge an AI agent needs to be productive in this repo.

**Big Picture:**
- **App type:** Small Flask web app served from `app.py`.
- **Storage:** All runtime state is filesystem-based (JSON and flat files) — see `users/`, `uploads_metadata.json`, `activity_log.json`, `family/family.json`, and `text_entries/`.
- **Static assets:** Images and videos live under `static/images/` and `static/videos/` respectively; uploaded generic files may be in `uploads/`.

**Key Files & Where to Look**
- `app.py`: central app, routes, auth logic, and all API handlers.
- `config.json`: local defaults for `MASTER_PASSWORD` and `SECRET_KEY` (production should use env vars).
- `requirements.txt`: `Flask==2.3.3`, `Werkzeug==2.3.7` — install with `pip install -r requirements.txt`.
- Templates: `templates/` mirrors routes (e.g., `text.html`, `admin_uploads.html`, `login.html`).
- Data folders: `users/` (per-user JSON), `text_entries/`, `family/`, `uploads/`, `static/`.

**Auth & Permissions (important)**
- Login is session-based. Normal users are stored in `users/<username>.json` with fields `{username, password (hashed), is_admin}`.
- A `MASTER_PASSWORD` (env or `config.json`) bypasses user passwords and creates `session['username']='sysop'` with `is_admin=True` — treat `MASTER_PASSWORD` as highly sensitive.

**Data patterns and invariants**
- Filenames are normalized: lowercased, spaces replaced with `_` (see upload handling in `app.py`).
- Upload metadata: `add_upload_record()` appends objects to `uploads_metadata.json` with keys `filename`, `type`, `uploader`, `assigned_to`, `upload_date`.
- Activity audit: `log_activity()` appends to `activity_log.json` (keeps last ~1000 entries).

**APIs & important routes to reference**
- Media listing: `GET /media/api/list` (collects from `static/images` and `static/videos`).
- Text management: `GET /text/api/list`, `GET /text/api/load/<filename>`, `POST /text/api/new`, `POST /text/api/save`, `DELETE /text/api/delete/<filename>`.
- Admin uploads endpoints: `/admin/uploads/api/list`, `/admin/uploads/api/reassign`, `/admin/uploads/api/delete` — require `is_admin`.

**Run / Debug locally**
- Install deps: `pip install -r requirements.txt`.
- Run directly: `python app.py` (app checks `FLASK_DEBUG` env var to enable debug). Example — PowerShell:

```powershell
$env:FLASK_DEBUG = 'true'
python .\app.py
```

or bash/cmd:

```bash
export FLASK_DEBUG=true
python app.py
```

**Important environment/config notes**
- `SECRET_KEY` and `MASTER_PASSWORD` are read from environment variables first, then `config.json` fallback. Avoid committing secrets to `config.json` in production.
- On Windows development environments, recommend using env vars rather than leaving `config.json` with secrets.

**Conventions & small gotchas**
- Many routes expect `session['username']` — creating or editing code should preserve that contract.
- Files and user records are manipulated directly on disk (no DB transactions). Be conservative when changing write logic and consider concurrent access.
- When adding features that touch uploads or users, update `uploads_metadata.json` and `activity_log.json` consistently using the existing helper functions to preserve format.

**Where tests / CI are (not) present**
- There are no tests or CI configuration in the repo. Keep changes small and test by running `python app.py` and exercising the relevant route in a browser.

**Examples for quick reference**
- To find where uploads are tracked: see `add_upload_record()` and `uploads_metadata.json`.
- To reproduce master-login behavior, inspect the top of `app.py` (lines that read `MASTER_PASSWORD`) and the `login()` handler which sets `session['username']='sysop'`.

If anything here looks incorrect or you want specific examples (route handlers, template patterns, or data-file schemas), tell me which area to expand and I'll update this file.
