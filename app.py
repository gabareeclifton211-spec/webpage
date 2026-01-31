import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
from flask import send_from_directory

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'images'),
        'favicon.png', mimetype='image/png')


# Use environment variable for secret key, fallback to config.json, then config.local.json
def load_config_key(key, default=None):
    # 1. Environment variable
    if key in os.environ:
        return os.environ[key]
    # 2. config.json
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            val = config.get(key)
            if val:
                return val
    except Exception as e:
        pass
    # 3. config.local.json
    try:
        with open("config.local.json", "r") as f:
            config = json.load(f)
            val = config.get(key)
            if val:
                return val
    except Exception as e:
        pass
    return default

app.secret_key = load_config_key("SECRET_KEY", "supersecretkey")

# Upload folder
UPLOAD_FOLDER = "uploads"
UPLOADS_METADATA = "uploads_metadata.json"
ACTIVITY_LOG = "activity_log.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# Ensure common runtime directories exist so file operations won't fail
os.makedirs("users", exist_ok=True)
os.makedirs("text_entries", exist_ok=True)
os.makedirs("family", exist_ok=True)
os.makedirs(os.path.join("static", "images"), exist_ok=True)
os.makedirs(os.path.join("static", "videos"), exist_ok=True)

# Create empty metadata/log files if they don't exist to avoid FileNotFoundError
if not os.path.exists(UPLOADS_METADATA):
    with open(UPLOADS_METADATA, "w") as f:
        json.dump([], f)

if not os.path.exists(ACTIVITY_LOG):
    with open(ACTIVITY_LOG, "w") as f:
        json.dump([], f)

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



# Load master password (env > config.json > config.local.json)
MASTER_PASSWORD = load_config_key("MASTER_PASSWORD", "changeme")


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


def infer_missing_relationships(member, family):
    """
    Infer missing relationships based on existing data.
    For example: If Jane (spouse of John) has child Mary, then John should also have Mary as child.
    """
    member_id = member["id"]
    id_to_member = {m["id"]: m for m in family if m["id"] != member_id}
    
    inferred_children = set(member.get("children", []))
    inferred_parents = set(member.get("parents", []))
    inferred_siblings = set(member.get("siblings", []))
    
    # Infer children from spouse's children
    for spouse_id in member.get("spouse", []):
        if spouse_id in id_to_member:
            spouse = id_to_member[spouse_id]
            # Add spouse's children as this member's children
            for child_id in spouse.get("children", []):
                if child_id != member_id:
                    inferred_children.add(child_id)
    
    # Infer siblings from parents
    for parent_id in member.get("parents", []):
        if parent_id in id_to_member:
            parent = id_to_member[parent_id]
            # All parent's children (except self) are siblings
            for child_id in parent.get("children", []):
                if child_id != member_id:
                    inferred_siblings.add(child_id)
    
    # Infer parents from siblings' parents
    for sibling_id in member.get("siblings", []):
        if sibling_id in id_to_member:
            sibling = id_to_member[sibling_id]
            # Siblings share parents
            for parent_id in sibling.get("parents", []):
                inferred_parents.add(parent_id)
    
    return {
        "children": sorted(list(inferred_children)),
        "parents": sorted(list(inferred_parents)),
        "siblings": sorted(list(inferred_siblings))
    }


def sync_siblings_in_family(family):
    id_to_member = {m["id"]: m for m in family}

    # Build sibling graph using explicit siblings and shared parents
    adjacency = {m["id"]: set() for m in family}

    # Explicit siblings
    for m in family:
        for sid in m.get("siblings", []):
            if sid in id_to_member and sid != m["id"]:
                adjacency[m["id"]].add(sid)
                adjacency[sid].add(m["id"])

    # Shared parents imply siblings
    parent_map = {}
    for m in family:
        for pid in m.get("parents", []):
            parent_map.setdefault(pid, set()).add(m["id"])

    for siblings_set in parent_map.values():
        for mid in siblings_set:
            adjacency[mid].update(siblings_set - {mid})

    # Find connected components and apply full sibling lists
    visited = set()
    for member_id in adjacency.keys():
        if member_id in visited:
            continue
        stack = [member_id]
        component = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            stack.extend(adjacency[current] - visited)

        for mid in component:
            id_to_member[mid]["siblings"] = sorted(component - {mid})


def sync_spouses_in_family(family):
    id_to_member = {m["id"]: m for m in family}
    for m in family:
        for sid in list(m.get("spouse", [])):
            if sid in id_to_member and sid != m["id"]:
                other = id_to_member[sid]
                if m["id"] not in other.get("spouse", []):
                    other.setdefault("spouse", []).append(m["id"])
            else:
                # Remove invalid spouse IDs
                m["spouse"] = [i for i in m.get("spouse", []) if i in id_to_member and i != m["id"]]





@app.route("/admin/sync-siblings")
@login_required
def admin_sync_siblings():
    if not session.get("is_admin"):
        return "Access denied"

    family_file = os.path.join("family", "family.json")
    if not os.path.exists(family_file):
        return "Family data not found"

    with open(family_file, "r") as f:
        family = json.load(f)

    sync_siblings_in_family(family)
    sync_spouses_in_family(family)

    with open(family_file, "w") as f:
        json.dump(family, f, indent=4)

    log_activity("SYNC_SIBLINGS", session.get("username"), "Siblings lists normalized")
    return redirect("/family")





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
    # Sort alphabetically by first name, then last name
    family = sorted(family, key=lambda m: (m.get('first_name', '').lower(), m.get('last_name', '').lower()))
    return render_template("family.html", family=family, is_admin=session.get("is_admin", False))


@app.route("/admin/delete_member/<int:member_id>", methods=["POST"])
@login_required
def admin_delete_member(member_id):
    if not session.get("is_admin"):
        return "Access denied"

    family_file = os.path.join("family", "family.json")
    if not os.path.exists(family_file):
        return redirect("/family")

    with open(family_file, "r") as f:
        family = json.load(f)

    member = next((m for m in family if m["id"] == member_id), None)
    if not member:
        return redirect("/family")

    # Remove member from family list
    family = [m for m in family if m["id"] != member_id]

    # Remove references from other members
    for m in family:
        for key in ("parents", "children", "siblings", "spouse"):
            if member_id in m.get(key, []):
                m[key] = [i for i in m.get(key, []) if i != member_id]

    # Clean up member photo if it exists and is a local file
    photo = member.get("photo")
    if photo and photo.startswith("/static/images/"):
        photo_path = os.path.join(app.root_path, photo.lstrip("/"))
        if os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except OSError:
                pass

    # Normalize sibling lists after removal
    sync_siblings_in_family(family)

    with open(family_file, "w") as f:
        json.dump(family, f, indent=4)

    log_activity("DELETE_MEMBER", session.get("username"), f"Deleted member ID {member_id}")
    return redirect("/family")


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


        def resolve_to_ids(val, family, next_id, rel_type, this_member_id=None):
            if not val:
                return [], next_id
            result = []
            for entry in val.split(","):
                entry = entry.strip()
                if entry.isdigit():
                    result.append(int(entry))
                else:
                    # Try to match by name (first and last)
                    found = False
                    for m in family:
                        full_name = f"{m['first_name'].strip()} {m['last_name'].strip()}".lower()
                        if entry.lower() == full_name:
                            result.append(m['id'])
                            found = True
                            break
                    if not found and entry:
                        # Auto-add placeholder member
                        parts = entry.split()
                        first = parts[0] if len(parts) > 0 else "Unknown"
                        last = parts[-1] if len(parts) > 1 else "Unknown"
                        placeholder = {
                            "id": next_id,
                            "first_name": first,
                            "middle_name": "",
                            "maiden_name": "",
                            "other_names": "",
                            "last_name": last,
                            "suffix": "",
                            "birth_date": "",
                            "death_date": None,
                            "gender": "unknown",
                            "parents": [],
                            "children": [],
                            "spouse": [],
                            "siblings": [],
                            "photo": None,
                            "bio": "Auto-added placeholder. Update this member's info."
                        }
                        # Link this member to the placeholder reciprocally
                        if rel_type == "parents" and this_member_id is not None:
                            placeholder["children"] = [this_member_id]
                        elif rel_type == "children" and this_member_id is not None:
                            placeholder["parents"] = [this_member_id]
                        elif rel_type == "spouse" and this_member_id is not None:
                            placeholder["spouse"] = [this_member_id]
                        elif rel_type == "siblings" and this_member_id is not None:
                            placeholder["siblings"] = [this_member_id]
                        family.append(placeholder)
                        result.append(next_id)
                        next_id += 1
            return result, next_id

        # Resolve relationships, auto-adding placeholders as needed
        next_id = new_id + 1
        parents, next_id = resolve_to_ids(request.form.get("parents", ""), family, next_id, "parents", new_id)
        children, next_id = resolve_to_ids(request.form.get("children", ""), family, next_id, "children", new_id)
        siblings, next_id = resolve_to_ids(request.form.get("siblings", ""), family, next_id, "siblings", new_id)
        spouse, next_id = resolve_to_ids(request.form.get("spouse", ""), family, next_id, "spouse", new_id)

        # Handle photo upload
        photo_url = None
        if "photo" in request.files:
            file = request.files["photo"]
            if file and file.filename:
                ext = os.path.splitext(file.filename)[1].lower()
                safe_name = f"member_{new_id}_{os.urandom(8).hex()}{ext}"
                save_path = os.path.join("static", "images", safe_name)
                file.save(save_path)
                photo_url = safe_name  # Store just the filename, not the full path

        member = {
            "id": new_id,
            "first_name": request.form["first_name"],
            "middle_name": request.form.get("middle_name", ""),
            "maiden_name": request.form.get("maiden_name", ""),
            "other_names": request.form.get("other_names", ""),
            "last_name": request.form["last_name"],
            "suffix": request.form.get("suffix", ""),
            "birth_date": request.form["birth_date"],
            "death_date": request.form.get("death_date") or None,
            "gender": request.form["gender"],
            "parents": parents,
            "children": children,
            "siblings": siblings,
            "spouse": spouse,
            "photo": photo_url,
            "bio": request.form.get("bio", "")
        }

        family.append(member)
        
        # Propagate children to spouses automatically
        id_to_member = {m["id"]: m for m in family}
        for m in family:
            for spouse_id in m.get("spouse", []):
                if spouse_id in id_to_member:
                    spouse = id_to_member[spouse_id]
                    # Add this member's children to spouse's children
                    for child_id in m.get("children", []):
                        if child_id not in spouse.get("children", []):
                            spouse.setdefault("children", []).append(child_id)
                    # Add spouse's children to this member's children
                    for child_id in spouse.get("children", []):
                        if child_id not in m.get("children", []):
                            m.setdefault("children", []).append(child_id)
        
        # Ensure sibling and spouse lists are symmetric across all related members
        sibling_ids = set(siblings)
        for m in family:
            if m["id"] == new_id:
                continue
            if m["id"] in sibling_ids:
                current = set(m.get("siblings", []))
                current.add(new_id)
                current.update(sibling_ids - {m["id"]})
                m["siblings"] = sorted(current)
        sync_spouses_in_family(family)
        # Resort family to ensure all are visible and sorted
        family = sorted(family, key=lambda m: (m.get('first_name', '').lower(), m.get('last_name', '').lower()))
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
        def resolve_to_ids_auto(val, family, next_id, rel_type, this_member_id=None):
            if not val:
                return [], next_id
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
                    # Try to match by name (first and last)
                    found = False
                    for m in family:
                        full_name = f"{m['first_name'].strip()} {m['last_name'].strip()}".lower()
                        if entry.lower() == full_name:
                            result.append(m['id'])
                            found = True
                            break
                    if not found and entry:
                        # Auto-add placeholder member
                        parts = entry.split()
                        first = parts[0] if len(parts) > 0 else "Unknown"
                        last = parts[-1] if len(parts) > 1 else "Unknown"
                        placeholder = {
                            "id": next_id,
                            "first_name": first,
                            "middle_name": "",
                            "maiden_name": "",
                            "other_names": "",
                            "last_name": last,
                            "suffix": "",
                            "birth_date": "",
                            "death_date": None,
                            "gender": "unknown",
                            "parents": [],
                            "children": [],
                            "spouse": [],
                            "siblings": [],
                            "photo": None,
                            "bio": "Auto-added placeholder. Update this member's info."
                        }
                        # Link this member to the placeholder reciprocally
                        if rel_type == "parents" and this_member_id is not None:
                            placeholder["children"] = [this_member_id]
                        elif rel_type == "children" and this_member_id is not None:
                            placeholder["parents"] = [this_member_id]
                        elif rel_type == "spouse" and this_member_id is not None:
                            placeholder["spouse"] = [this_member_id]
                        elif rel_type == "siblings" and this_member_id is not None:
                            placeholder["siblings"] = [this_member_id]
                        family.append(placeholder)
                        result.append(next_id)
                        next_id += 1
            # Add reciprocal links for existing members (after processing all entries)
            for eid in result:
                for m in family:
                    if m["id"] == eid and this_member_id is not None:
                        if rel_type == "parents":
                            if this_member_id not in m.get("children", []):
                                m.setdefault("children", []).append(this_member_id)
                        elif rel_type == "children":
                            if this_member_id not in m.get("parents", []):
                                m.setdefault("parents", []).append(this_member_id)
                        elif rel_type == "spouse":
                            if this_member_id not in m.get("spouse", []):
                                m.setdefault("spouse", []).append(this_member_id)
                        elif rel_type == "siblings":
                            if this_member_id not in m.get("siblings", []):
                                m.setdefault("siblings", []).append(this_member_id)
            return result, next_id

        # Find the next available ID for new placeholders
        next_id = max([m["id"] for m in family], default=0) + 1
        # Auto-add and resolve relationships
        siblings_input = request.form.get("siblings", "")
        parents, next_id = resolve_to_ids_auto(request.form.get("parents", ""), family, next_id, "parents", member_id)
        children, next_id = resolve_to_ids_auto(request.form.get("children", ""), family, next_id, "children", member_id)
        siblings, next_id = resolve_to_ids_auto(siblings_input, family, next_id, "siblings", member_id)
        spouse, next_id = resolve_to_ids_auto(request.form.get("spouse", ""), family, next_id, "spouse", member_id)

        # Handle photo upload or preserve existing
        photo_url = None
        if "photo" in request.files:
            file = request.files["photo"]
            if file and file.filename:
                ext = os.path.splitext(file.filename)[1].lower()
                safe_name = f"member_{member_id}_{os.urandom(8).hex()}{ext}"
                save_path = os.path.join("static", "images", safe_name)
                file.save(save_path)
                photo_url = safe_name  # Store just the filename, not the full path

        # Update the member in the family list
        updated = False
        for i, m in enumerate(family):
            if m["id"] == member_id:
                family[i]["first_name"] = request.form["first_name"]
                family[i]["middle_name"] = request.form.get("middle_name", "")
                family[i]["maiden_name"] = request.form.get("maiden_name", "")
                family[i]["other_names"] = request.form.get("other_names", "")
                family[i]["last_name"] = request.form["last_name"]
                family[i]["suffix"] = request.form.get("suffix", "")
                family[i]["birth_date"] = request.form["birth_date"]
                family[i]["death_date"] = request.form.get("death_date") or None
                family[i]["gender"] = request.form["gender"]
                family[i]["parents"] = parents
                family[i]["children"] = children
                family[i]["siblings"] = siblings
                family[i]["spouse"] = spouse
                family[i]["bio"] = request.form.get("bio", "")
                if photo_url:
                    family[i]["photo"] = photo_url
                elif "photo" in family[i] and family[i]["photo"]:
                    # Preserve existing photo if no new upload
                    pass
                else:
                    family[i]["photo"] = None
                updated = True
                break
        # Ensure sibling and spouse lists are normalized after edits
        if updated:
            # Propagate children to spouses
            id_to_member = {m["id"]: m for m in family}
            for m in family:
                for spouse_id in m.get("spouse", []):
                    if spouse_id in id_to_member:
                        spouse = id_to_member[spouse_id]
                        # Add this member's children to spouse's children
                        for child_id in m.get("children", []):
                            if child_id not in spouse.get("children", []):
                                spouse.setdefault("children", []).append(child_id)
                        # Add spouse's children to this member's children
                        for child_id in spouse.get("children", []):
                            if child_id not in m.get("children", []):
                                m.setdefault("children", []).append(child_id)
            
            sync_siblings_in_family(family)
            sync_spouses_in_family(family)
        # Resort family to keep consistent order
        family = sorted(family, key=lambda m: (m.get('first_name', '').lower(), m.get('last_name', '').lower()))
        if updated:
            with open(family_file, "w") as f:
                json.dump(family, f, indent=4)
        return redirect("/family")
    
    # GET request: Infer missing relationships for display
    inferred = infer_missing_relationships(member, family)
    
    # Merge inferred with existing (don't overwrite explicit entries)
    member["_inferred_children"] = inferred["children"]
    member["_inferred_parents"] = inferred["parents"]
    member["_inferred_siblings"] = inferred["siblings"]
    
    return render_template("edit_member.html", member=member, family=family)


# -------------------------------
# View Family Member
# -------------------------------
@app.route("/family/view/<int:member_id>")
@app.route("/view_member/<int:member_id>")
@login_required
def view_member(member_id):
    family_file = os.path.join("family", "family.json")
    family = []
    if os.path.exists(family_file):
        with open(family_file, "r") as f:
            family = json.load(f)
    
    member = next((m for m in family if m["id"] == member_id), None)
    if not member:
        return "Member not found", 404
    
    id_to_member = {m["id"]: m for m in family}
    
    # Add photo URLs - prepend path if not already there
    if member.get("photo") and not member["photo"].startswith("/"):
        member["photo_url"] = f"/static/images/{member['photo']}"
        member["photo_thumb_url"] = f"/static/images/{member['photo']}"
    else:
        member["photo_url"] = member.get("photo")
        member["photo_thumb_url"] = member.get("photo")
    
    # Get related members with photo URLs
    parents = []
    for pid in member.get("parents", []):
        if pid in id_to_member:
            p = id_to_member[pid].copy()
            if p.get("photo") and not p["photo"].startswith("/"):
                p["photo_thumb_url"] = f"/static/images/{p['photo']}"
            else:
                p["photo_thumb_url"] = p.get("photo")
            parents.append(p)
    
    children = []
    for cid in member.get("children", []):
        if cid in id_to_member:
            c = id_to_member[cid].copy()
            if c.get("photo") and not c["photo"].startswith("/"):
                c["photo_thumb_url"] = f"/static/images/{c['photo']}"
            else:
                c["photo_thumb_url"] = c.get("photo")
            children.append(c)
    
    spouses = []
    for sid in member.get("spouse", []):
        if sid in id_to_member:
            s = id_to_member[sid].copy()
            if s.get("photo") and not s["photo"].startswith("/"):
                s["photo_thumb_url"] = f"/static/images/{s['photo']}"
            else:
                s["photo_thumb_url"] = s.get("photo")
            spouses.append(s)
    
    siblings = []
    for sibid in member.get("siblings", []):
        if sibid in id_to_member:
            sib = id_to_member[sibid].copy()
            if sib.get("photo") and not sib["photo"].startswith("/"):
                sib["photo_thumb_url"] = f"/static/images/{sib['photo']}"
            else:
                sib["photo_thumb_url"] = sib.get("photo")
            siblings.append(sib)
    
    return render_template("view_member.html", 
                          member=member, 
                          parents=parents, 
                          children=children, 
                          spouses=spouses,
                          siblings=siblings)


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
    search_name = request.args.get("search", "").strip()
    relationships = []
    selected_member = None
    if search_name:
        # Find member by name (case-insensitive, first + last)
        selected_member = next((m for m in family if f"{m.get('first_name','').strip()} {m.get('last_name','').strip()}".lower() == search_name.lower()), None)
        if selected_member:
            for other in family:
                if other["id"] == selected_member["id"]:
                    continue
                rel = get_relationship(selected_member["id"], other["id"], family)
                relationships.append({
                    "member_name": f"{other.get('first_name','')} {other.get('last_name','')}",
                    "relationship": rel
                })
    return render_template("relationships.html", family=family, search_name=search_name, relationships=relationships)


# -------------------------------
# ADMIN: Merge Duplicates
# -------------------------------
@app.route("/admin/merge-duplicates", methods=["GET", "POST"])
@login_required
def admin_merge_duplicates():
    if not session.get("is_admin"):
        return "Access denied", 403

    family_file = os.path.join("family", "family.json")
    if not os.path.exists(family_file):
        return "Family data not found", 404

    if request.method == "POST":
        # Handle merge submission
        if not request.form.get("confirm"):
            return "Please confirm the merge", 400

        primary_id = int(request.form.get("primary_id"))
        duplicate_ids_str = request.form.get("duplicate_ids", "")
        duplicate_ids = [int(x.strip()) for x in duplicate_ids_str.split(",") if x.strip()]

        if primary_id not in duplicate_ids:
            return "Primary ID must be one of the duplicates", 400

        # Create backup before merge
        import shutil
        from datetime import datetime as dt
        backup_file = os.path.join("family", f"family_before_merge_{dt.now().strftime('%Y%m%d_%H%M%S')}.json")
        shutil.copy(family_file, backup_file)

        # Load family data
        with open(family_file, "r") as f:
            family = json.load(f)

        # Find members
        primary = None
        duplicates = []
        for member in family:
            if member["id"] == primary_id:
                primary = member
            elif member["id"] in duplicate_ids:
                duplicates.append(member)

        if not primary:
            return "Primary member not found", 404

        # Merge relationships from duplicates into primary
        for dup in duplicates:
            # Merge parents
            for parent_id in dup.get("parents", []):
                if parent_id not in primary.get("parents", []):
                    primary.setdefault("parents", []).append(parent_id)
            
            # Merge children
            for child_id in dup.get("children", []):
                if child_id not in primary.get("children", []):
                    primary.setdefault("children", []).append(child_id)
            
            # Merge spouse
            for spouse_id in dup.get("spouse", []):
                if spouse_id not in primary.get("spouse", []):
                    primary.setdefault("spouse", []).append(spouse_id)
            
            # Merge siblings
            for sib_id in dup.get("siblings", []):
                if sib_id not in primary.get("siblings", []) and sib_id != primary_id:
                    primary.setdefault("siblings", []).append(sib_id)

            # Preserve photo if primary doesn't have one
            if not primary.get("photo") and dup.get("photo"):
                primary["photo"] = dup["photo"]

            # Preserve bio if primary doesn't have one
            if not primary.get("bio") and dup.get("bio"):
                primary["bio"] = dup["bio"]

        # Update all references in other family members to point to primary
        for member in family:
            if member["id"] == primary_id or member["id"] in duplicate_ids:
                continue

            # Update parents references
            if "parents" in member:
                member["parents"] = [primary_id if pid in duplicate_ids else pid for pid in member["parents"]]
                member["parents"] = list(set(member["parents"]))  # Remove duplicates

            # Update children references
            if "children" in member:
                member["children"] = [primary_id if cid in duplicate_ids else cid for cid in member["children"]]
                member["children"] = list(set(member["children"]))

            # Update spouse references
            if "spouse" in member:
                member["spouse"] = [primary_id if sid in duplicate_ids else sid for sid in member["spouse"]]
                member["spouse"] = list(set(member["spouse"]))

            # Update siblings references
            if "siblings" in member:
                member["siblings"] = [primary_id if sid in duplicate_ids else sid for sid in member["siblings"]]
                member["siblings"] = list(set(member["siblings"]))

        # Remove duplicate members from family list
        family = [m for m in family if m["id"] not in duplicate_ids or m["id"] == primary_id]

        # Clean up primary's own relationships (remove self-references and invalid IDs)
        valid_ids = {m["id"] for m in family}
        primary["parents"] = [i for i in primary.get("parents", []) if i in valid_ids and i != primary_id]
        primary["children"] = [i for i in primary.get("children", []) if i in valid_ids and i != primary_id]
        primary["spouse"] = [i for i in primary.get("spouse", []) if i in valid_ids and i != primary_id]
        primary["siblings"] = [i for i in primary.get("siblings", []) if i in valid_ids and i != primary_id]

        # Save updated family data
        with open(family_file, "w") as f:
            json.dump(family, f, indent=4)

        # Log the merge
        merged_names = ", ".join([f"{d.get('first_name', '')} {d.get('last_name', '')} (ID {d['id']})" for d in duplicates if d["id"] != primary_id])
        log_activity(
            "MERGE_DUPLICATES",
            session.get("username"),
            f"Merged {merged_names} into {primary.get('first_name', '')} {primary.get('last_name', '')} (ID {primary_id})"
        )

        return redirect("/family")

    # GET request: Find duplicates
    with open(family_file, "r") as f:
        family = json.load(f)

    # Group members by matching key fields
    duplicate_groups = []
    seen = set()

    for i, member in enumerate(family):
        if member["id"] in seen:
            continue

        # Create a key based on name and birth date
        key = (
            member.get("first_name", "").strip().lower(),
            member.get("last_name", "").strip().lower(),
            member.get("birth_date", "")
        )

        # Find all members with the same key
        matches = []
        for j, other in enumerate(family):
            other_key = (
                other.get("first_name", "").strip().lower(),
                other.get("last_name", "").strip().lower(),
                other.get("birth_date", "")
            )
            if other_key == key and other_key != ("", "", ""):
                matches.append(other)
                seen.add(other["id"])

        # Only include groups with 2+ members
        if len(matches) > 1:
            duplicate_groups.append(matches)

    # Helper function for template
    def display_name(member):
        name_parts = []
        if member.get("first_name"):
            name_parts.append(member["first_name"])
        if member.get("middle_name"):
            name_parts.append(member["middle_name"])
        if member.get("last_name"):
            name_parts.append(member["last_name"])
        if member.get("suffix"):
            name_parts.append(member["suffix"])
        return " ".join(name_parts) or "Unnamed"

    return render_template("admin_merge_duplicates.html", duplicate_groups=duplicate_groups, display_name=display_name)


# -------------------------------
# Run App
# -------------------------------
if __name__ == "__main__":
    # In production (PythonAnywhere), this won't run
    # Use debug=False for production
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode)
