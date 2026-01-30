
# AI Coding Agent Onboarding: Project-Specific Instructions

This guide provides actionable, up-to-date knowledge for AI coding agents working in this repository. **Focus on these patterns, conventions, and workflows to be productive immediately.**

## Big Picture & Architecture
- **Type:** Single-file Flask web app (`app.py`), serving HTML templates and static assets.
- **State:** All runtime and persistent data is stored as JSON or flat files on disk (no database).
- **Key Data Folders:**
	- `users/`: Per-user JSON records (`username`, hashed `password`, `is_admin`)
	- `uploads/`, `uploads_metadata.json`: Uploaded files and their metadata
	- `activity_log.json`: Audit log (last ~1000 actions)
	- `family/family.json`, `text_entries/`: Family and text entry data
	- `static/images/`, `static/videos/`: Media assets

## Core Files & Patterns
- **`app.py`:**
	- All routes, API endpoints, and authentication logic are here
	- Helper functions: `add_upload_record()`, `log_activity()` (always use these for uploads/audit)
- **Templates:**
	- Located in `templates/`, named to match routes (e.g., `login.html`, `admin_uploads.html`)
- **Config:**
	- `config.json` (local dev), but `SECRET_KEY` and `MASTER_PASSWORD` are loaded from environment variables if set
	- Never commit secrets to version control
- **Requirements:**
	- `Flask==2.3.3`, `Werkzeug==2.3.7` (see `requirements.txt`)

## Auth, Permissions, and Security
- **Session-based login:**
	- User records in `users/<username>.json` (fields: `username`, `password` (hashed), `is_admin`)
	- `MASTER_PASSWORD` (from env/config) allows admin override, sets `session['username']='sysop'` and `is_admin=True`
- **Admin-only endpoints:**
	- All `/admin/*` routes require `is_admin` in session

## Data Handling & Invariants
- **Filenames:** Always normalized (lowercase, spaces to `_`)
- **Uploads:**
	- Metadata appended to `uploads_metadata.json` via `add_upload_record()`
	- Deletion/reassignment must update both file and metadata
- **Audit:**
	- All user actions logged via `log_activity()`

## API & Route Reference
- **Media:** `GET /media/api/list` (lists images/videos)
- **Text:** `GET /text/api/list`, `GET /text/api/load/<filename>`, `POST /text/api/new`, `POST /text/api/save`, `DELETE /text/api/delete/<filename>`
- **Admin Uploads:** `/admin/uploads/api/list`, `/admin/uploads/api/reassign`, `/admin/uploads/api/delete` (admin only)

## Local Development Workflow
- **Install:** `pip install -r requirements.txt`
- **Run:** `python app.py` (set `FLASK_DEBUG=true` for debug mode)
	- PowerShell: `$env:FLASK_DEBUG = 'true'; python .\app.py`
	- Bash/cmd: `export FLASK_DEBUG=true; python app.py`
- **No automated tests or CI:**
	- Test changes by running the app and using the browser

## Project Conventions & Gotchas
- **Session contract:** Most routes require `session['username']` to be set
- **Direct file I/O:** No DB transactions; be careful with concurrent writes
- **Always update both metadata and logs** when modifying uploads or users
- **No test/CI infra:** Keep changes small and test manually

## Examples
- **Upload tracking:** See `add_upload_record()` in `app.py` and `uploads_metadata.json`
- **Master login:** See `MASTER_PASSWORD` logic and `login()` in `app.py`

---
If you need more detail on any area (route handlers, template usage, data schemas), specify which topic to expand.
