
# AI Coding Agent Onboarding: Project-Specific Instructions

This guide provides actionable, up-to-date knowledge for AI coding agents working in this repository. **Focus on these patterns, conventions, and workflows to be productive immediately.**

## Big Picture & Architecture
- **Type:** Single-file Flask web app (`app.py`, ~1340 lines), serving HTML templates and static assets
- **State:** All runtime and persistent data stored as JSON or flat files on disk (no database)
- **Key features:** Family tree management, text entry CRUD, media galleries, upload tracking, admin dashboard
- **Key Data Folders:**
	- `users/`: Per-user JSON records (`username`, hashed `password`, `is_admin`)
	- `uploads/`, `uploads_metadata.json`: Uploaded files and their metadata (images/videos/text)
	- `activity_log.json`: Audit log (last ~1000 actions, auto-trimmed)
	- `family/family.json`: Family tree data (members with relationships: parents, children, spouse, siblings)
	- `text_entries/`: User-created text files (`.txt`)
	- `static/images/`, `static/videos/`: Media assets (referenced by family members and served publicly)

## Core Files & Patterns
- **`app.py` (all routes and logic):**
	- Routes: `/`, `/login`, `/register`, `/upload`, `/text`, `/media`, `/images`, `/videos`, `/family`, `/admin/*`
	- Helper functions: `add_upload_record()`, `log_activity()`, `get_storage_stats()` (always use these for uploads/audit/stats)
	- Config loading: `load_config_key(key, default)` (env → config.json → config.local.json fallback chain)
	- Decorator: `@login_required` (redirects to `/login` if no `session['username']`)
- **Templates (`templates/`):**
	- `base.html`: Standard layout with nav bar, flash messages, mobile-responsive nav toggle
	- Named to match routes: `login.html`, `admin_uploads.html`, `family.html`, `text.html`, etc.
	- Family tree templates: `family.html`, `add_member.html`, `edit_member.html`, `view_member.html`, `relationships.html`
- **Static Assets (`static/`):**
	- `forms.js`: Client-side validation (password length, match, email format)
	- `text_manager.js`: SPA-style text editor (AJAX calls to `/text/api/*`)
	- `nav.js`: Mobile nav toggle logic
	- `style.css`: Global styles
- **Config:**
	- `config.json` (local dev), `config.local.json` (local overrides, gitignored)
	- `SECRET_KEY` and `MASTER_PASSWORD` loaded from env vars if set (recommended for production)
	- Never commit secrets to version control
- **Requirements:** `Flask==2.3.3`, `Werkzeug==2.3.7`, `Pillow==10.0.1` (see `requirements.txt`)

## Auth, Permissions, and Security
- **Session-based login:**
	- User records in `users/<username>.json` (fields: `username`, `password` (Werkzeug hashed), `is_admin`)
	- `MASTER_PASSWORD` (from env/config) allows admin override → sets `session['username']='sysop'` and `is_admin=True`
	- Session keys: `username`, `is_admin` (checked by `@login_required` and admin routes)
- **Admin-only endpoints:**
	- All `/admin/*` routes require `is_admin=True` in session (no explicit decorator, checked inline)
	- Examples: `/admin/users`, `/admin/dashboard`, `/admin/uploads`, `/admin/edit/<username>`, `/admin/merge-duplicates`

## Data Handling & Invariants
- **Filenames:** Always normalized (lowercase, spaces replaced with `_`) via `secure_filename()`
- **Uploads:**
	- Metadata appended to `uploads_metadata.json` via `add_upload_record(filename, file_type, uploader)`
	- Fields: `filename`, `type` (image/video/text/other), `uploader`, `assigned_to`, `upload_date` (timestamp)
	- Deletion/reassignment must update both file and metadata (see `/admin/uploads/api/delete`, `/admin/uploads/api/reassign`)
- **Audit:**
	- All user actions logged via `log_activity(action, username, details="")`
	- Auto-trimmed to last 1000 entries (see `log_activity()` in `app.py`)
	- Logged events: LOGIN, LOGIN_FAILED, UPLOAD, DELETE_FILE, REASSIGN_FILE, etc.
- **Family data (`family/family.json`):**
	- Array of member objects with fields: `id`, `first_name`, `last_name`, `middle_name`, `suffix`, `birth_date`, `death_date`, `gender`, `parents` (array of IDs), `children` (array), `spouse` (array), `siblings` (array), `photo` (path), `bio`, `maiden_name`, `other_names`
	- Relationships are **bidirectional**: when adding a parent, update both parent's `children` and child's `parents`
	- Sibling sync: `/admin/sync-siblings` endpoint recalculates siblings based on shared parents

## API & Route Reference
- **Media:**
	- `GET /media/api/list` → JSON `{images: [...], videos: [...]}`
	- `GET /images`, `GET /videos` → HTML galleries
- **Text (AJAX-driven by `text_manager.js`):**
	- `GET /text/api/list` → JSON `{files: [...]}`
	- `GET /text/api/load/<filename>` → JSON `{content: "..."}`
	- `POST /text/api/new` → Create new text entry (JSON body: `{title, content}`)
	- `POST /text/api/save` → Update existing entry (JSON body: `{filename, content}`)
	- `DELETE /text/api/delete/<filename>` → Delete entry
- **Family:**
	- `GET /family` → List all members
	- `POST /family/add` → Add new member (form data, handles photo upload)
	- `GET /family/view/<id>`, `GET /family/edit/<id>`, `POST /family/update/<id>` → CRUD ops
	- `POST /family/delete/<id>` → Delete member (also removes photo file)
	- `GET /relationships?search=<name>` → Show relationships for a member
- **Admin Uploads (admin only):**
	- `GET /admin/uploads/api/list` → JSON list of all uploads with metadata
	- `POST /admin/uploads/api/reassign` → Reassign file to different user (JSON: `{filename, new_user}`)
	- `POST /admin/uploads/api/delete` → Delete file (JSON: `{filename}`)
- **Admin Dashboard:**
	- `GET /admin/dashboard` → Admin overview
	- `GET /admin/api/stats` → JSON storage stats (`total_size`, `by_type`, `by_user`, `file_count`)
	- `GET /admin/api/activity` → JSON recent activity log

## Local Development Workflow
- **Install:** `pip install -r requirements.txt`
- **Run:** `python app.py` (set `FLASK_DEBUG=true` for debug mode)
	- PowerShell: `$env:FLASK_DEBUG = 'true'; python .\app.py`
	- Bash/cmd: `export FLASK_DEBUG=true; python app.py`
	- Server runs on `http://127.0.0.1:5000` by default
- **No automated tests or CI:**
	- Test changes by running the app and using the browser
	- No test suite, no GitHub Actions (manual testing only)
- **Deployment:** See `DEPLOYMENT_GUIDE.md` for PythonAnywhere setup

## Project Conventions & Gotchas
- **Session contract:** Most routes require `session['username']` to be set (enforced by `@login_required`)
- **Direct file I/O:** No DB transactions; be careful with concurrent writes (potential race conditions on metadata files)
- **Always update both metadata and logs** when modifying uploads or users
- **No test/CI infra:** Keep changes small and test manually
- **Mobile nav:** Uses CSS class toggles (`nav-open` on `<body>`) for mobile menu, with inline fallback in `base.html`
- **Text editor:** SPA-style (no page reloads), all CRUD via AJAX to `/text/api/*`
- **Family relationships:** Must maintain bidirectional consistency (see `/family/update/<id>` and `/admin/sync-siblings`)

## Examples
- **Upload tracking:** See `add_upload_record()` in `app.py` (lines 77-87) and `uploads_metadata.json`
- **Master login:** See `MASTER_PASSWORD` logic in `login()` (lines 214-219 in `app.py`)
- **Activity logging:** See `log_activity()` (lines 100-112 in `app.py`) and usage in routes
- **Storage stats:** See `get_storage_stats()` (lines 115-152 in `app.py`) for filesystem analysis
- **Family relationships:** See `get_relationship()` helper (lines 1260-1300 in `app.py`) for relationship inference logic

---
**Need more detail?** Specify a topic (route handlers, template usage, data schemas, deployment) to expand.
