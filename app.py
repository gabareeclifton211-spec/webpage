import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Use environment variable for secret key, fallback to config for local development
if 'SECRET_KEY' in os.environ:
    app.secret_key = os.environ['SECRET_KEY']
else:
    # Try to load from config.json for local development
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            app.secret_key = config.get("SECRET_KEY", "supersecretkey")
    except Exception as e:
        print(f"Warning reading config.json for SECRET_KEY: {e}")
        app.secret_key = "supersecretkey"

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


# Load master password
if 'MASTER_PASSWORD' in os.environ:
    MASTER_PASSWORD = os.environ['MASTER_PASSWORD']
else:
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            MASTER_PASSWORD = config["MASTER_PASSWORD"]
    except Exception as e:
        print(f"Warning reading config.json for MASTER_PASSWORD: {e}")
        MASTER_PASSWORD = "changeme"  # Fallback, should be set in production


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

        if password != confirm_password:
            return "Passwords do not match."

        user_file = os.path.join("users", f"{username}.json")
        if os.path.exists(user_file):
            return "Username already taken."

        user_data = {
            "username": username,
            "password": generate_password_hash(password),
            "is_admin": False
        }

        with open(user_file, "w") as f:
            json.dump(user_data, f, indent=4)

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
        user_file = os.path.join("users", f"{username}.json")

        if not os.path.exists(user_file):
            log_activity("LOGIN_FAILED", username, "User does not exist")
            return "User does not exist"

        with open(user_file, "r") as f:
            user_data = json.load(f)

        if check_password_hash(user_data["password"], password):
            session["username"] = username
            session["is_admin"] = user_data.get("is_admin", False)
            log_activity("LOGIN", username, f"Role: {'Admin' if user_data.get('is_admin') else 'User'}")
            return redirect("/")

        log_activity("LOGIN_FAILED", username, "Incorrect password")
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
                "is_admin": data.get("is_admin", False)
            })

    return render_template("admin_users.html", users=users)


@app.route("/admin/toggle/<username>")
@login_required
def toggle_admin(username):
    if not session.get("is_admin"):
        return "Access denied"

    filepath = os.path.join("users", f"{username}.json")
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

    if username == "sysop":
        return "Cannot delete sysop"

    filepath = os.path.join("users", f"{username}.json")
    if os.path.exists(filepath):
        os.remove(filepath)

    return redirect("/admin/users")


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
    
    # Check if user exists
    user_file = os.path.join("users", f"{new_user}.json")
    if not os.path.exists(user_file):
        return {"status": "error", "message": "User does not exist"}
    
    metadata = load_upload_metadata()
    
    # Find and update the upload record
    for item in metadata:
        if item["filename"] == filename:
            old_user = item.get("assigned_to")
            item["assigned_to"] = new_user
            save_upload_metadata(metadata)
            log_activity("FILE_REASSIGN", session.get("username"), f"File: {filename} from {old_user} to {new_user}")
            return {"status": "ok", "message": f"File assigned to {new_user}"}
    
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
    return render_template("family.html", family=family)


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
            "photo": None,
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
# Run App
# -------------------------------
if __name__ == "__main__":
    # In production (PythonAnywhere), this won't run
    # Use debug=False for production
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode)
