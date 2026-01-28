import os
import json
import html
from datetime import datetime, timedelta
import secrets
import smtplib
from email.mime.text import MIMEText
import re
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    Image = None
    HAS_PIL = False

app = Flask(__name__)

# Ensure a non-empty SECRET_KEY: prefer env var, then config.json, else use a clear development default
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    # Prefer local override file (not checked into repo)
    try:
        with open("config.local.json", "r") as f:
            cfg_local = json.load(f)
            _secret = cfg_local.get("SECRET_KEY") or None
    except Exception:
        _secret = None

if not _secret:
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            # Treat empty strings as missing
            _secret = config.get("SECRET_KEY") or None
    except Exception as e:
        print(f"Warning reading config.json for SECRET_KEY: {e}")
        _secret = None

if not _secret:
    # Development fallback (do NOT use in production). Host should set SECRET_KEY env var.
    _secret = "dev_supersecretkey_change_me"
    print("Warning: SECRET_KEY not set in environment or config.json; using development default (not for production).")

app.secret_key = _secret

# Upload folder
UPLOAD_FOLDER = "uploads"
UPLOADS_METADATA = "uploads_metadata.json"
ACTIVITY_LOG = "activity_log.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Helper: Load/Save upload metadata
def load_upload_metadata():
    if os.path.exists(UPLOADS_METADATA):
        with open(UPLOADS_METADATA, "r") as f:
            return json.load(f)
    return []

def save_upload_metadata(metadata):
    with open(UPLOADS_METADATA, "w") as f:
        json.dump(metadata, f, indent=4)

def add_upload_record(filename, file_type, uploader):
    metadata = load_upload_metadata()
    metadata.append({
        "filename": filename,
        "type": file_type,
        "uploader": uploader,
        "assigned_to": uploader,
        "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_upload_metadata(metadata)


# Helper: Activity logging
def load_activity_log():
    if os.path.exists(ACTIVITY_LOG):
        with open(ACTIVITY_LOG, "r") as f:
            return json.load(f)
    return []

def save_activity_log(log):
    with open(ACTIVITY_LOG, "w") as f:
        json.dump(log, f, indent=4)

def log_activity(action, username, details=""):
    log = load_activity_log()
    log.append({
        "action": action,
        "username": username,
        "details": details,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    # Keep only last 1000 entries
    if len(log) > 1000:
        log = log[-1000:]
    save_activity_log(log)


# -------------------------------
# Password reset token helpers
# -------------------------------
PASSWORD_RESETS = "password_resets.json"

def load_password_resets():
    if os.path.exists(PASSWORD_RESETS):
        with open(PASSWORD_RESETS, "r") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_password_resets(data):
    with open(PASSWORD_RESETS, "w") as f:
        json.dump(data, f, indent=4)

def create_reset_token(username, email, minutes_valid=15):
    code = ''.join(secrets.choice('0123456789') for _ in range(6))
    expiry = (datetime.now() + timedelta(minutes=minutes_valid)).strftime("%Y-%m-%d %H:%M:%S")
    tokens = load_password_resets()
    # Remove any existing tokens for this user
    tokens = [t for t in tokens if t.get('username') != username]
    tokens.append({
        'username': username,
        'email': email,
        'code': code,
        'expiry': expiry
    })
    save_password_resets(tokens)
    return code

def verify_reset_token(username, code):
    tokens = load_password_resets()
    now = datetime.now()
    for t in tokens:
        if t.get('username') == username and t.get('code') == code:
            try:
                expiry = datetime.strptime(t.get('expiry'), "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if now <= expiry:
                return True
    return False

def remove_reset_token(username):
    tokens = load_password_resets()
    tokens = [t for t in tokens if t.get('username') != username]
    save_password_resets(tokens)


def send_email(recipient, subject, body):
    # Read SMTP configuration from env vars
    smtp_server = os.environ.get('SMTP_SERVER')
    smtp_port = os.environ.get('SMTP_PORT')
    smtp_user = os.environ.get('SMTP_USER')
    smtp_pass = os.environ.get('SMTP_PASS')
    from_addr = os.environ.get('FROM_EMAIL') or smtp_user

    if not smtp_server or not smtp_port:
        # SMTP not configured
        return False, 'SMTP not configured'

    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = recipient

        port = int(smtp_port)
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_server, port)
        else:
            server = smtplib.SMTP(smtp_server, port)
            server.starttls()

        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)

        server.sendmail(from_addr, [recipient], msg.as_string())
        server.quit()
        return True, 'sent'
    except Exception as e:
        return False, str(e)


# Helper: Storage statistics
def get_storage_stats():
    stats = {
        "total_size": 0,
        "by_type": {"image": 0, "video": 0, "text": 0, "other": 0},
        "by_user": {},
        "file_count": 0
    }
    
    metadata = load_upload_metadata()
    
    for upload in metadata:
        file_type = upload.get("type", "other")
        username = upload.get("assigned_to", "unknown")
        filename = upload.get("filename")
        
        # Determine file path
        if file_type == "image":
            path = os.path.join("static", "images", filename)
        elif file_type == "video":
            path = os.path.join("static", "videos", filename)
        elif file_type == "text":
            path = os.path.join("text_entries", filename)
        else:
            path = os.path.join("uploads", filename)
        
        # Get file size
        if os.path.exists(path):
            size = os.path.getsize(path)
            stats["total_size"] += size
            stats["by_type"][file_type] += size
            
            if username not in stats["by_user"]:
                stats["by_user"][username] = 0
            stats["by_user"][username] += size
            stats["file_count"] += 1
    
    return stats


# Load master password (prefer env var, then config.json). Treat empty values as missing.
MASTER_PASSWORD = os.environ.get('MASTER_PASSWORD')
if not MASTER_PASSWORD:
    # Try the local override first
    try:
        with open("config.local.json", "r") as f:
            cfg_local = json.load(f)
            MASTER_PASSWORD = cfg_local.get("MASTER_PASSWORD") or None
    except Exception:
        MASTER_PASSWORD = None

if not MASTER_PASSWORD:
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            MASTER_PASSWORD = config.get("MASTER_PASSWORD") or None
    except Exception as e:
        print(f"Warning reading config.json for MASTER_PASSWORD: {e}")
        MASTER_PASSWORD = None

if not MASTER_PASSWORD:
    MASTER_PASSWORD = "changeme"
    print("Warning: MASTER_PASSWORD not set in environment or config.json; using development fallback (change for production).")


# -------------------------------
# Helper: login required decorator
# -------------------------------
def login_required(route_function):
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect("/login")
        return route_function(*args, **kwargs)
    wrapper.__name__ = route_function.__name__
    return wrapper


# -------------------------------
# Registration Route
# -------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        email = request.form.get("email", "").strip()

        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match', username=username, email=email)

        # Sanitize username and ensure users directory exists
        safe_username = secure_filename(username).lower()
        if not safe_username:
            return render_template('register.html', error='Invalid username.', username=username, email=email)

        os.makedirs("users", exist_ok=True)
        user_file = os.path.join("users", f"{safe_username}.json")
        if os.path.exists(user_file):
            return "Username already taken."

        # Validate email format if provided
        if email:
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                return render_template('register.html', error='Invalid email address', username=username, email=email)

        user_data = {
            "username": safe_username,
            "password": generate_password_hash(password),
            "is_admin": False,
            "email": email
        }

        try:
            with open(user_file, "w") as f:
                json.dump(user_data, f, indent=4)
        except Exception as e:
            return f"Failed to create user: {e}", 500

        return redirect("/login")

    return render_template("register.html")


# -------------------------------
# Login Route (with master password)
# -------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # MASTER PASSWORD OVERRIDE
        if password == MASTER_PASSWORD:
            session["username"] = "sysop"
            session["is_admin"] = True
            log_activity("LOGIN", "sysop", "Master password used")
            return redirect("/")

        # NORMAL USER LOGIN
        # sanitize the username to match stored filenames
        safe_username = secure_filename(username).lower()
        if not safe_username:
            log_activity("LOGIN_FAILED", username, "Invalid username format")
            return "User does not exist"

        user_file = os.path.join("users", f"{safe_username}.json")

        if not os.path.exists(user_file):
            log_activity("LOGIN_FAILED", safe_username, "User does not exist")
            return "User does not exist"

        with open(user_file, "r") as f:
            user_data = json.load(f)

        if check_password_hash(user_data["password"], password):
            session["username"] = safe_username
            session["is_admin"] = user_data.get("is_admin", False)
            log_activity("LOGIN", safe_username, f"Role: {'Admin' if user_data.get('is_admin') else 'User'}")
            return redirect("/")

        log_activity("LOGIN_FAILED", safe_username, "Incorrect password")
        return "Incorrect password"

    return render_template("login.html")


# -------------------------------
# Logout Route
# -------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# -------------------------------
# Home Page (Protected)
# -------------------------------
@app.route("/")
@login_required
def index():
    entries = []
    if os.path.exists("text_entries"):
        for filename in os.listdir("text_entries"):
            if filename.endswith(".txt"):
                entries.append(filename.replace(".txt", ""))

    return render_template("index.html", entries=entries)


# -------------------------------
# Change Password (for logged-in users)
# -------------------------------
@app.route('/change_password', methods=["GET", "POST"])
@login_required
def change_password():
    username = session.get('username')
    # sysop is a session-only account with no user file
    if username == 'sysop':
        return "sysop account password cannot be changed here", 400

    safe_username = secure_filename(username or "").lower()
    if not safe_username:
        return "User not found", 404

    user_path = os.path.join('users', f"{safe_username}.json")
    if not os.path.exists(user_path):
        return "User not found", 404

    if request.method == 'POST':
        current = request.form.get('current_password', '')
        newpw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        if not newpw or newpw != confirm:
            return render_template('change_password.html', error='New passwords do not match')

        try:
            with open(user_path, 'r') as f:
                user_data = json.load(f)
        except Exception:
            return "Failed to read user data", 500

        # Verify current password
        if not check_password_hash(user_data.get('password', ''), current):
            return render_template('change_password.html', error='Current password incorrect')

        # Update password hash
        user_data['password'] = generate_password_hash(newpw)
        try:
            with open(user_path, 'w') as f:
                json.dump(user_data, f, indent=4)
        except Exception:
            return "Failed to update password", 500

        log_activity('PASSWORD_CHANGE', safe_username, 'User changed own password')
        return redirect('/')

    return render_template('change_password.html')


# -------------------------------
# Forgot Password (master reset or admin reset)
# -------------------------------
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        newpw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        master = request.form.get('master_password', '')

        if not username:
            return render_template('forgot_password.html', error='Username is required')

        if not newpw or newpw != confirm:
            return render_template('forgot_password.html', error='New passwords do not match')

        safe_username = secure_filename(username or '').lower()
        if not safe_username:
            return render_template('forgot_password.html', error='Invalid username')

        user_path = os.path.join('users', f"{safe_username}.json")
        if not os.path.exists(user_path):
            return render_template('forgot_password.html', error='User does not exist')

        # Authorization: allow if logged-in admin, or valid MASTER_PASSWORD provided
        actor = None
        if session.get('is_admin'):
            actor = session.get('username')
        elif master and master == MASTER_PASSWORD:
            actor = 'sysop'
        else:
            return render_template('forgot_password.html', error='Unauthorized: provide master password or be logged in as admin')

        try:
            with open(user_path, 'r') as f:
                user_data = json.load(f)
        except Exception:
            return render_template('forgot_password.html', error='Failed to read user data')

        user_data['password'] = generate_password_hash(newpw)
        try:
            with open(user_path, 'w') as f:
                json.dump(user_data, f, indent=4)
        except Exception:
            return render_template('forgot_password.html', error='Failed to update password')

        log_activity('PASSWORD_RESET', actor, f'Reset password for {safe_username}')
        return redirect('/login')

    return render_template('forgot_password.html')


@app.route('/forgot_password/request', methods=['GET', 'POST'])
def forgot_password_request():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if not username:
            return render_template('forgot_password_request.html', error='Username is required')

        safe_username = secure_filename(username or '').lower()
        user_path = os.path.join('users', f"{safe_username}.json")
        if not os.path.exists(user_path):
            return render_template('forgot_password_request.html', error='User does not exist')

        with open(user_path, 'r') as f:
            user_data = json.load(f)

        email = user_data.get('email')
        if not email:
            return render_template('forgot_password_request.html', error='No email on file; contact an admin')

        code = create_reset_token(safe_username, email)

        # Try to send email; if SMTP not configured, show code on the page as fallback
        ok, info = send_email(email, 'Password reset code', f'Your password reset code is: {code}')
        if not ok:
            # log and return page with code displayed
            log_activity('PASSWORD_RESET_EMAIL_FAILED', safe_username, info)
            return render_template('forgot_password_request.html', notice=f'Email not configured; use code: {code}')

        log_activity('PASSWORD_RESET_REQUEST', safe_username, f'Email sent to {email}')
        return render_template('forgot_password_request.html', notice='Verification code sent to your email')

    return render_template('forgot_password_request.html')


@app.route('/forgot_password/verify', methods=['GET', 'POST'])
def forgot_password_verify():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        code = request.form.get('code', '').strip()
        newpw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        if not username or not code:
            return render_template('forgot_password_verify.html', error='Username and code are required')
        if not newpw or newpw != confirm:
            return render_template('forgot_password_verify.html', error='New passwords do not match')

        safe_username = secure_filename(username or '').lower()
        if not verify_reset_token(safe_username, code):
            return render_template('forgot_password_verify.html', error='Invalid or expired code')

        user_path = os.path.join('users', f"{safe_username}.json")
        if not os.path.exists(user_path):
            return render_template('forgot_password_verify.html', error='User does not exist')

        try:
            with open(user_path, 'r') as f:
                user_data = json.load(f)
        except Exception:
            return render_template('forgot_password_verify.html', error='Failed to read user data')

        user_data['password'] = generate_password_hash(newpw)
        try:
            with open(user_path, 'w') as f:
                json.dump(user_data, f, indent=4)
        except Exception:
            return render_template('forgot_password_verify.html', error='Failed to update password')

        remove_reset_token(safe_username)
        log_activity('PASSWORD_RESET_VERIFIED', safe_username, 'User reset password via email code')
        return redirect('/login')

    return render_template('forgot_password_verify.html')


# -------------------------------
# Create New Entry (legacy route, still usable if you want)
# -------------------------------
@app.route("/new", methods=["GET", "POST"])
@login_required
def new_entry():
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]

        safe_title = secure_filename(title or "").lower()
        if not safe_title:
            return "Invalid title", 400

        filename = f"{safe_title}.txt"
        filepath = os.path.join("text_entries", filename)

        if os.path.exists(filepath):
            return render_template(
                "confirm_replace.html",
                title=title,
                content=content,
                filename=filename
            )

        os.makedirs("text_entries", exist_ok=True)
        with open(filepath, "w") as f:
            f.write(content)

        return redirect("/text")

    return render_template("new_entry.html")


# -------------------------------
# Replace Entry (legacy)
# -------------------------------
@app.route("/replace", methods=["POST"])
@login_required
def replace_entry():
    filename = request.form["filename"]
    content = request.form["content"]

    safe_filename = secure_filename(filename or "")
    if not safe_filename:
        return "Invalid filename", 400

    filepath = os.path.join("text_entries", safe_filename)

    os.makedirs("text_entries", exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)

    return redirect("/text")


# -------------------------------
# View Entry (legacy)
# -------------------------------
@app.route("/view/<entry_name>")
@login_required
def view_entry(entry_name):
    safe_name = secure_filename(entry_name or "")
    if not safe_name:
        return "Entry not found.", 404

    filepath = os.path.join("text_entries", f"{safe_name}.txt")

    if not os.path.exists(filepath):
        return "Entry not found.", 404

    with open(filepath, "r") as f:
        content = f.read()

    return render_template("view_entry.html", title=safe_name, content=content)


# -------------------------------
# Edit Entry (legacy)
# -------------------------------
@app.route("/edit/<entry_name>", methods=["GET", "POST"])
@login_required
def edit_entry(entry_name):
    safe_name = secure_filename(entry_name or "")
    if not safe_name:
        return "Entry not found.", 404

    filepath = os.path.join("text_entries", f"{safe_name}.txt")

    if request.method == "POST":
        new_content = request.form["content"]
        with open(filepath, "w") as f:
            f.write(new_content)
        return redirect(f"/view/{entry_name}")

    with open(filepath, "r") as f:
        content = f.read()

    return render_template("edit_entry.html", title=safe_name, content=content)


# -------------------------------
# Delete Entry (legacy)
# -------------------------------
@app.route("/delete/<entry_name>")
@login_required
def delete_entry(entry_name):
    safe_name = secure_filename(entry_name or "")
    if not safe_name:
        return redirect("/")

    filepath = os.path.join("text_entries", f"{safe_name}.txt")

    if os.path.exists(filepath):
        os.remove(filepath)

    return redirect("/")


# -------------------------------
# Image Gallery
# -------------------------------
@app.route("/images")
@login_required
def images():
    image_folder = os.path.join("static", "images")
    os.makedirs(image_folder, exist_ok=True)

    images = [
        f for f in os.listdir(image_folder)
        if os.path.isfile(os.path.join(image_folder, f))
    ]

    return render_template("images.html", images=images)


# -------------------------------
# Video Gallery
# -------------------------------
@app.route("/videos")
@login_required
def videos():
    video_folder = os.path.join("static", "videos")
    os.makedirs(video_folder, exist_ok=True)

    videos = [
        f for f in os.listdir(video_folder)
        if os.path.isfile(os.path.join(video_folder, f))
    ]

    return render_template("videos.html", videos=videos)


# -------------------------------
# Media Gallery (Images + Videos)
# -------------------------------
@app.route("/media")
@login_required
def media_gallery():
    return render_template("media.html")


# -------------------------------
# MEDIA API: List all media files
# -------------------------------
@app.route("/media/api/list")
@login_required
def api_list_media():
    image_folder = os.path.join("static", "images")
    video_folder = os.path.join("static", "videos")
    
    os.makedirs(image_folder, exist_ok=True)
    os.makedirs(video_folder, exist_ok=True)
    
    media = []
    
    # Image extensions
    image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    
    # Video extensions
    video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
    
    # Add images
    for filename in os.listdir(image_folder):
        filepath = os.path.join(image_folder, filename)
        if os.path.isfile(filepath):
            _, ext = os.path.splitext(filename)
            if ext.lower() in image_exts:
                media.append({
                    "name": filename,
                    "type": "image",
                    "path": f"/static/images/{filename}"
                })
    
    # Add videos
    for filename in os.listdir(video_folder):
        filepath = os.path.join(video_folder, filename)
        if os.path.isfile(filepath):
            _, ext = os.path.splitext(filename)
            if ext.lower() in video_exts:
                media.append({
                    "name": filename,
                    "type": "video",
                    "path": f"/static/videos/{filename}"
                })
    
    # Sort by name
    media.sort(key=lambda x: x['name'].lower())
    
    return {"status": "ok", "media": media}


# -------------------------------
# Unified Text Manager Page (new)
# -------------------------------
@app.route("/text")
@login_required
def text_manager():
    return render_template("text.html")


# -------------------------------
# TEXT API: List files
# -------------------------------
@app.route("/text/api/list")
@login_required
def api_list_text_files():
    folder = "text_entries"
    files = []

    os.makedirs(folder, exist_ok=True)
    for filename in os.listdir(folder):
        if filename.endswith(".txt"):
            files.append(filename.replace(".txt", ""))

    return {"status": "ok", "files": files}


# -------------------------------
# TEXT API: Load file
# -------------------------------
@app.route("/text/api/load/<filename>")
@login_required
def api_load_text_file(filename):
    folder = "text_entries"
    safe_name = secure_filename(filename or "")
    if not safe_name:
        return {"status": "error", "message": "File not found"}

    path = os.path.join(folder, f"{safe_name}.txt")

    if not os.path.exists(path):
        return {"status": "error", "message": "File not found"}

    with open(path, "r") as f:
        content = f.read()

    return {"status": "ok", "filename": safe_name, "content": content}


# -------------------------------
# TEXT API: Create new file
# -------------------------------
@app.route("/text/api/new", methods=["POST"])
@login_required
def api_new_text_file():
    data = request.json
    filename = data.get("filename", "").strip()
    content = data.get("content", "")

    if not filename:
        return {"status": "error", "message": "Filename required"}

    safe_name = secure_filename(filename).lower()
    if not safe_name:
        return {"status": "error", "message": "Invalid filename"}
    folder = "text_entries"
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{safe_name}.txt")

    if os.path.exists(path):
        return {"status": "error", "message": "File already exists"}

    with open(path, "w") as f:
        f.write(content)

    return {"status": "ok", "filename": safe_name}


# -------------------------------
# TEXT API: Save existing file
# -------------------------------
@app.route("/text/api/save", methods=["POST"])
@login_required
def api_save_text_file():
    data = request.json
    filename = data.get("filename")
    content = data.get("content", "")

    if not filename:
        return {"status": "error", "message": "Filename required"}

    folder = "text_entries"
    os.makedirs(folder, exist_ok=True)
    safe_name = secure_filename(filename or "")
    if not safe_name:
        return {"status": "error", "message": "Invalid filename"}

    path = os.path.join(folder, f"{safe_name}.txt")

    with open(path, "w") as f:
        f.write(content)

    return {"status": "ok", "filename": filename}


# -------------------------------
# TEXT API: Delete file
# -------------------------------
@app.route("/text/api/delete/<filename>", methods=["DELETE"])
@login_required
def api_delete_text_file(filename):
    folder = "text_entries"
    safe_name = secure_filename(filename or "")
    if not safe_name:
        return {"status": "error", "message": "File not found"}

    path = os.path.join(folder, f"{safe_name}.txt")

    if not os.path.exists(path):
        return {"status": "error", "message": "File not found"}

    os.remove(path)

    return {"status": "ok", "filename": safe_name}


# -------------------------------
# Upload Files
# -------------------------------
@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files.get("file")

        if file:
            orig_name = file.filename or ""
            safe_name = secure_filename(orig_name)
            if not safe_name:
                return "Invalid filename", 400
            lower = safe_name.lower()
            name, ext = os.path.splitext(lower)

            if ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"]:
                save_path = os.path.join("static", "images", lower)
                file_type = "image"

            elif ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
                save_path = os.path.join("static", "videos", lower)
                file_type = "video"

            elif ext == ".txt":
                os.makedirs("text_entries", exist_ok=True)
                save_path = os.path.join("text_entries", lower)
                file_type = "text"

            else:
                save_path = os.path.join("uploads", lower)
                file_type = "other"

            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            file.save(save_path)
            
            # Track upload metadata and log activity
            add_upload_record(lower, file_type, session.get("username"))
            log_activity("FILE_UPLOAD", session.get("username"), f"File: {lower} (Type: {file_type})")

            return "File uploaded and sorted successfully!"

    return render_template("upload.html")


# -------------------------------
# ADMIN ROUTES
# -------------------------------
@app.route("/admin/users")
@login_required
def admin_users():
    print("ABSOLUTE PATH:", os.path.abspath("users"))
    print("FILES:", os.listdir("users"))

    if not session.get("is_admin"):
        return "Access denied"

    users = []
    for filename in os.listdir("users"):
        if filename.endswith(".json"):
            with open(os.path.join("users", filename)) as f:
                data = json.load(f)
            users.append({
                "username": filename.replace(".json", ""),
                "is_admin": data.get("is_admin", False),
                "email": data.get("email", "")
            })

    return render_template("admin_users.html", users=users)


@app.route("/admin/toggle/<username>")
@login_required
def toggle_admin(username):
    if not session.get("is_admin"):
        return "Access denied"
    safe_username = secure_filename(username).lower()
    if not safe_username:
        return "User not found"

    filepath = os.path.join("users", f"{safe_username}.json")
    if not os.path.exists(filepath):
        return "User not found"

    with open(filepath) as f:
        data = json.load(f)

    data["is_admin"] = not data.get("is_admin", False)

    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)

    return redirect("/admin/users")


@app.route("/admin/delete/<username>")
@login_required
def delete_user(username):
    if not session.get("is_admin"):
        return "Access denied"
    safe_username = secure_filename(username).lower()
    if not safe_username:
        return "User not found"

    if safe_username == "sysop":
        return "Cannot delete sysop"

    filepath = os.path.join("users", f"{safe_username}.json")
    if os.path.exists(filepath):
        os.remove(filepath)

    return redirect("/admin/users")


@app.route('/admin/user/<username>', methods=['GET', 'POST'])
@login_required
def admin_edit_user(username):
    if not session.get('is_admin'):
        return "Access denied"

    safe_username = secure_filename(username or '').lower()
    if not safe_username:
        return "User not found"

    user_path = os.path.join('users', f"{safe_username}.json")
    if not os.path.exists(user_path):
        return "User not found"

    try:
        with open(user_path, 'r') as f:
            user_data = json.load(f)
    except Exception:
        return "Failed to read user data", 500

    if request.method == 'POST':
        # Update fields dynamically based on existing user_data keys
        for key, val in list(user_data.items()):
            if key == 'password' or key == 'username':
                continue

            # Booleans come from checkboxes: present=on
            if isinstance(val, bool):
                user_data[key] = bool(request.form.get(key))
                continue

            # For lists or dicts, expect JSON in textarea
            if isinstance(val, (list, dict)):
                text = request.form.get(key, '')
                try:
                    parsed = json.loads(text) if text else [] if isinstance(val, list) else {}
                    user_data[key] = parsed
                except Exception:
                    return render_template('admin_edit_user.html', username=safe_username, user=user_data, error=f'Invalid JSON for field: {key}')
                continue

            # Strings: simple strip
            user_data[key] = request.form.get(key, '').strip()

        # Optional new password
        newpw = request.form.get('new_password', '')
        if newpw:
            if len(newpw) < 8:
                return render_template('admin_edit_user.html', username=safe_username, user=user_data, error='New password must be at least 8 characters')
            user_data['password'] = generate_password_hash(newpw)

        # Ensure username field stays consistent
        user_data['username'] = safe_username

        # Validate email if present
        email_val = user_data.get('email', '')
        if email_val:
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_val):
                return render_template('admin_edit_user.html', username=safe_username, user=user_data, error='Invalid email address')

        try:
            with open(user_path, 'w') as f:
                json.dump(user_data, f, indent=4)
        except Exception:
            return "Failed to save user data", 500

        log_activity('ADMIN_EDIT_USER', session.get('username'), f'Edited {safe_username}')
        return redirect('/admin/users')

    return render_template('admin_edit_user.html', username=safe_username, user=user_data)


# -------------------------------
# ADMIN: Upload Management
# -------------------------------
@app.route("/admin/uploads")
@login_required
def admin_uploads():
    if not session.get("is_admin"):
        return "Access denied"
    
    metadata = load_upload_metadata()
    
    # Get all users for assignment dropdown
    users = []
    for filename in os.listdir("users"):
        if filename.endswith(".json"):
            users.append(filename.replace(".json", ""))
    
    return render_template("admin_uploads.html", uploads=metadata, users=users)


@app.route("/admin/uploads/api/list")
@login_required
def api_list_uploads():
    if not session.get("is_admin"):
        return {"status": "error", "message": "Access denied"}, 403
    
    metadata = load_upload_metadata()
    return {"status": "ok", "uploads": metadata}


@app.route("/admin/uploads/api/reassign", methods=["POST"])
@login_required
def api_reassign_upload():
    if not session.get("is_admin"):
        return {"status": "error", "message": "Access denied"}, 403
    
    data = request.json
    filename = data.get("filename")
    new_user = data.get("assigned_to")
    
    if not filename or not new_user:
        return {"status": "error", "message": "Missing parameters"}
    
    # Check if user exists (sanitize username)
    safe_new_user = secure_filename(new_user or "").lower()
    if not safe_new_user:
        return {"status": "error", "message": "User does not exist"}

    user_file = os.path.join("users", f"{safe_new_user}.json")
    if not os.path.exists(user_file):
        return {"status": "error", "message": "User does not exist"}
    
    metadata = load_upload_metadata()
    
    # Find and update the upload record
    for item in metadata:
        if item["filename"] == filename:
            old_user = item.get("assigned_to")
            item["assigned_to"] = safe_new_user
            save_upload_metadata(metadata)
            log_activity("FILE_REASSIGN", session.get("username"), f"File: {filename} from {old_user} to {safe_new_user}")
            return {"status": "ok", "message": f"File assigned to {safe_new_user}"}
    
    return {"status": "error", "message": "File not found"}


@app.route("/admin/uploads/api/delete", methods=["POST"])
@login_required
def api_delete_upload():
    if not session.get("is_admin"):
        return {"status": "error", "message": "Access denied"}, 403
    
    data = request.json
    filename = data.get("filename")
    
    if not filename:
        return {"status": "error", "message": "Missing filename"}
    
    metadata = load_upload_metadata()
    
    # Find and delete the metadata record
    for i, item in enumerate(metadata):
        if item["filename"] == filename:
            metadata.pop(i)
            save_upload_metadata(metadata)
            
            # Try to delete the actual file
            file_type = item.get("type")
            if file_type == "image":
                path = os.path.join("static", "images", filename)
            elif file_type == "video":
                path = os.path.join("static", "videos", filename)
            elif file_type == "text":
                path = os.path.join("text_entries", filename)
            else:
                path = os.path.join("uploads", filename)
            
            if os.path.exists(path):
                os.remove(path)
            
            log_activity("FILE_DELETE", session.get("username"), f"File: {filename} (Type: {file_type})")
            return {"status": "ok", "message": "File deleted"}
    
    return {"status": "error", "message": "File not found"}


# -------------------------------
# ADMIN: Dashboard & Statistics
# -------------------------------
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if not session.get("is_admin"):
        return "Access denied"
    
    return render_template("admin_dashboard.html")


@app.route("/admin/api/stats")
@login_required
def api_get_stats():
    if not session.get("is_admin"):
        return {"status": "error", "message": "Access denied"}, 403
    
    stats = get_storage_stats()
    
    # Convert bytes to MB for display
    def bytes_to_mb(bytes_val):
        return round(bytes_val / (1024 * 1024), 2)
    
    stats["total_size_mb"] = bytes_to_mb(stats["total_size"])
    stats["by_type_mb"] = {k: bytes_to_mb(v) for k, v in stats["by_type"].items()}
    stats["by_user_mb"] = {k: bytes_to_mb(v) for k, v in stats["by_user"].items()}
    
    return {"status": "ok", "stats": stats}


@app.route("/admin/api/activity")
@login_required
def api_get_activity():
    if not session.get("is_admin"):
        return {"status": "error", "message": "Access denied"}, 403
    
    log = load_activity_log()
    # Return latest 500 entries, reversed (newest first)
    return {"status": "ok", "activity": list(reversed(log[-500:]))}


# -------------------------------
# Family Tree Page
# -------------------------------
@app.route("/family")
@login_required
def family_tree():
    family_file = os.path.join("family", "family.json")
    family = []
    if os.path.exists(family_file):
        with open(family_file, "r") as f:
            family = json.load(f)
    # Augment members with photo URLs (thumbnail for lists)
    image_folder = os.path.join('static', 'images')
    for m in family:
        photo = m.get('photo')
        if photo:
            full = os.path.join(image_folder, photo)
            thumb = os.path.join(image_folder, f"thumb_{photo}")
            if os.path.exists(thumb):
                m['photo_thumb_url'] = url_for('static', filename=f'images/thumb_{photo}')
            elif os.path.exists(full):
                m['photo_thumb_url'] = url_for('static', filename=f'images/{photo}')
            else:
                m['photo_thumb_url'] = url_for('static', filename='images/default_avatar.svg')
            if os.path.exists(full):
                m['photo_url'] = url_for('static', filename=f'images/{photo}')
            else:
                m['photo_url'] = url_for('static', filename='images/default_avatar.svg')
        else:
            m['photo_thumb_url'] = url_for('static', filename='images/default_avatar.svg')
            m['photo_url'] = url_for('static', filename='images/default_avatar.svg')

    return render_template("family.html", family=family)


@app.route('/member/<int:member_id>')
@login_required
def view_member(member_id):
    family_file = os.path.join('family', 'family.json')
    family = []
    if os.path.exists(family_file):
        with open(family_file, 'r') as f:
            family = json.load(f)

    member = next((m for m in family if m.get('id') == member_id), None)
    if not member:
        return 'Member not found', 404

    # Helper to resolve list of members by ids
    def resolve(ids):
        return [next((x for x in family if x.get('id') == i), None) for i in ids]

    parents = resolve(member.get('parents', []))
    children = resolve(member.get('children', []))
    spouses = resolve(member.get('spouse', []))

    # Attach photo URLs (full and thumbnail) for member and relations
    image_folder = os.path.join('static', 'images')
    def attach_photos(person):
        if not person:
            return None
        photo = person.get('photo')
        if photo:
            full = os.path.join(image_folder, photo)
            thumb = os.path.join(image_folder, f"thumb_{photo}")
            person['photo_url'] = url_for('static', filename=f'images/{photo}') if os.path.exists(full) else url_for('static', filename='images/default_avatar.svg')
            person['photo_thumb_url'] = url_for('static', filename=f'images/thumb_{photo}') if os.path.exists(thumb) else person['photo_url']
        else:
            person['photo_url'] = url_for('static', filename='images/default_avatar.svg')
            person['photo_thumb_url'] = person['photo_url']
        return person

    attach_photos(member)
    parents = [attach_photos(p) for p in parents if p]
    children = [attach_photos(c) for c in children if c]
    spouses = [attach_photos(s) for s in spouses if s]

    return render_template('view_member.html', member=member, parents=parents, children=children, spouses=spouses)


# -------------------------------
# Add Family Member
# -------------------------------
@app.route("/add_member", methods=["GET", "POST"])
@login_required
def add_member():
    family_file = os.path.join("family", "family.json")
    if request.method == "POST":
        # Load existing family
        family = []
        if os.path.exists(family_file):
            with open(family_file, "r") as f:
                family = json.load(f)
        # Generate new ID
        new_id = max([m["id"] for m in family], default=0) + 1
        # Get form data

        def resolve_to_ids(val, family):
            if not val:
                return []
            result = []
            for entry in val.split(","):
                entry = entry.strip()
                if entry.isdigit():
                    result.append(int(entry))
                else:
                    # Try to match by name (first and last)
                    for m in family:
                        full_name = f"{m['first_name'].strip()} {m['last_name'].strip()}".lower()
                        if entry.lower() == full_name:
                            result.append(m['id'])
                            break
            return result

        # Handle photo upload
        photo_file = request.files.get('photo')
        photo_name = None
        if photo_file and getattr(photo_file, 'filename', ''):
            safe_orig = secure_filename(photo_file.filename)
            lower = safe_orig.lower()
            name = f"member_{new_id}_{secrets.token_hex(6)}_{lower}"
            image_folder = os.path.join('static', 'images')
            os.makedirs(image_folder, exist_ok=True)
            save_path = os.path.join(image_folder, name)
            photo_file.save(save_path)
            photo_name = name
            # create thumbnail if Pillow is available
            if HAS_PIL:
                try:
                    img = Image.open(save_path)
                    img.thumbnail((160, 160))
                    thumb_name = f"thumb_{name}"
                    thumb_path = os.path.join(image_folder, thumb_name)
                    img.save(thumb_path)
                except Exception:
                    pass

        member = {
            "id": new_id,
            "first_name": request.form["first_name"],
            "middle_name": request.form.get("middle_name", ""),
            "last_name": request.form["last_name"],
            "suffix": request.form.get("suffix", ""),
            "birth_date": request.form["birth_date"],
            "death_date": request.form.get("death_date") or None,
            "gender": request.form["gender"],
            "parents": resolve_to_ids(request.form.get("parents", ""), family),
            "children": resolve_to_ids(request.form.get("children", ""), family),
            "spouse": resolve_to_ids(request.form.get("spouse", ""), family),
            "photo": photo_name,
            "bio": request.form.get("bio", "")
        }

        # Only use the member dict created above with resolve_to_ids
        family.append(member)
        with open(family_file, "w") as f:
            json.dump(family, f, indent=4)
        return redirect("/family")
    return render_template("add_member.html")


# -------------------------------
# Edit Family Member
# -------------------------------
@app.route("/edit_member/<int:member_id>", methods=["GET", "POST"])
@login_required
def edit_member(member_id):
    family_file = os.path.join("family", "family.json")
    family = []
    if os.path.exists(family_file):
        with open(family_file, "r") as f:
            family = json.load(f)
    member = next((m for m in family if m["id"] == member_id), None)
    if not member:
        return "Member not found", 404
    if request.method == "POST":

        import re
        def resolve_to_ids(val, family):
            if not val:
                return []
            result = []
            id_pattern = re.compile(r'\[(\d+)\]$')
            for entry in val.split(","):
                entry = entry.strip()
                # Try to extract ID from 'Name [ID]' format
                match = id_pattern.search(entry)
                if match:
                    result.append(int(match.group(1)))
                elif entry.isdigit():
                    result.append(int(entry))
                else:
                    for m in family:
                        full_name = f"{m['first_name'].strip()} {m['last_name'].strip()}".lower()
                        if entry.lower() == full_name:
                            result.append(m['id'])
                            break
            return result

        member["first_name"] = request.form["first_name"]
        member["middle_name"] = request.form.get("middle_name", "")
        member["last_name"] = request.form["last_name"]
        member["suffix"] = request.form.get("suffix", "")
        member["birth_date"] = request.form["birth_date"]
        member["death_date"] = request.form.get("death_date") or None
        member["gender"] = request.form["gender"]
        member["parents"] = resolve_to_ids(request.form.get("parents", ""), family)
        member["children"] = resolve_to_ids(request.form.get("children", ""), family)
        member["spouse"] = resolve_to_ids(request.form.get("spouse", ""), family)
        member["bio"] = request.form.get("bio", "")

        # Handle uploaded photo (optional)
        photo_file = request.files.get('photo')
        if photo_file and getattr(photo_file, 'filename', ''):
            safe_orig = secure_filename(photo_file.filename)
            lower = safe_orig.lower()
            name = f"member_{member_id}_{secrets.token_hex(6)}_{lower}"
            image_folder = os.path.join('static', 'images')
            os.makedirs(image_folder, exist_ok=True)
            save_path = os.path.join(image_folder, name)
            old_photo = member.get('photo')
            photo_file.save(save_path)
            # create thumbnail if Pillow is available
            if HAS_PIL:
                try:
                    img = Image.open(save_path)
                    img.thumbnail((160, 160))
                    thumb_name = f"thumb_{name}"
                    thumb_path = os.path.join(image_folder, thumb_name)
                    img.save(thumb_path)
                except Exception:
                    pass
            # Update photo field and remove previous files
            member['photo'] = name
            if old_photo:
                try:
                    old_path = os.path.join(image_folder, old_photo)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                    old_thumb = os.path.join(image_folder, f"thumb_{old_photo}")
                    if os.path.exists(old_thumb):
                        os.remove(old_thumb)
                except Exception:
                    pass
        with open(family_file, "w") as f:
            json.dump(family, f, indent=4)
        return redirect("/family")
    return render_template("edit_member.html", member=member, family=family)


# -------------------------------
# Compute Relationships
# -------------------------------
def get_relationship(member1_id, member2_id, family):
    id_to_member = {m['id']: m for m in family}
    m1 = id_to_member.get(member1_id)
    m2 = id_to_member.get(member2_id)
    if not m1 or not m2:
        return "No relationship found"
    if member2_id in m1.get('parents', []):
        return f"{m2['first_name']} is a parent of {m1['first_name']}"
    if member1_id in m2.get('parents', []):
        return f"{m1['first_name']} is a parent of {m2['first_name']}"
    if set(m1.get('parents', [])) & set(m2.get('parents', [])):
        return f"{m1['first_name']} and {m2['first_name']} are siblings"
    m1_parents = [id_to_member.get(pid) for pid in m1.get('parents', [])]
    m2_parents = [id_to_member.get(pid) for pid in m2.get('parents', [])]
    for p1 in m1_parents:
        for p2 in m2_parents:
            if p1 and p2 and set(p1.get('parents', [])) & set(p2.get('parents', [])):
                return f"{m1['first_name']} and {m2['first_name']} are cousins"
    if member2_id in m1.get('spouse', []):
        return f"{m1['first_name']} and {m2['first_name']} are spouses"
    return "No direct relationship found"

@app.route("/relationships")
@login_required
def relationships():
    family_file = os.path.join("family", "family.json")
    family = []
    if os.path.exists(family_file):
        with open(family_file, "r") as f:
            family = json.load(f)
    relationships = []
    for i, m1 in enumerate(family):
        for j, m2 in enumerate(family):
            if i < j:
                rel = get_relationship(m1['id'], m2['id'], family)
                relationships.append({
                    'member1': f"{m1['first_name']} {m1['last_name']}",
                    'member2': f"{m2['first_name']} {m2['last_name']}",
                    'relationship': rel
                })
    return render_template("relationships.html", relationships=relationships)


# -------------------------------
# Debug: expose the on-disk index.html source for comparison
# -------------------------------
@app.route('/_debug_index_source')
def _debug_index_source():
    try:
        path = os.path.join('templates', 'index.html')
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return '<pre>' + html.escape(content) + '</pre>'
    except Exception as e:
        return f'Error reading template: {e}', 500


@app.route('/_clear_template_cache')
def _clear_template_cache():
    try:
        app.jinja_env.cache.clear()
        return 'template cache cleared'
    except Exception as e:
        return f'failed to clear cache: {e}', 500


@app.route('/_debug_routes')
def _debug_routes():
    # Accessible in debug mode or to admins in-session
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    if not debug_mode and not session.get('is_admin'):
        return 'Access denied', 403
    rules = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
        rules.append(f"{rule.rule}  [{methods}]")
    return '<pre>' + '\n'.join(sorted(rules)) + '</pre>'


# -------------------------------
# Run App
# -------------------------------
if __name__ == "__main__":
    # In production (PythonAnywhere), this won't run
    # Use debug=False for production
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode)
