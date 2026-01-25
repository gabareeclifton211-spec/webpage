# PythonAnywhere Deployment Guide

## Prerequisites

You'll need:
1. PythonAnywhere account (free at pythonanywhere.com)
2. All your project files
3. Strong passwords for admin/master password

---

## Step 1: Create PythonAnywhere Account

1. Go to **pythonanywhere.com**
2. Click "Start exploring PythonAnywhere"
3. Sign up for FREE account (or paid if preferred)
4. Verify your email

---

## Step 2: Upload Your Project Files

### Option A: Using GitHub (Recommended)

1. In PythonAnywhere, go to **Consoles** → **Bash**
2. Run these commands:
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

### Option B: Upload Manually via Web

1. Go to **Files** tab
2. Create new directory: `/home/yourusername/mysite`
3. Upload all files:
   - app.py
   - requirements.txt
   - config.json
   - templates/
   - static/
   - (Keep empty): users/, uploads/, text_entries/

---

## Step 3: Create Initial Directories

In **Bash Console**, run:
```bash
cd ~/mysite
mkdir -p users uploads text_entries/uploads/{images,videos,text}
mkdir -p static/images static/videos
```

---

## Step 4: Set Up Web App in PythonAnywhere

1. Go to **Web** tab
2. Click **Add a new web app**
3. Choose **Manual configuration**
4. Select **Python 3.10** (or latest available)
5. Click through the setup

---

## Step 5: Configure WSGI File

1. In **Web** tab, find **WSGI configuration file**
2. Click the link to edit it
3. Replace the entire content with:

```python
import sys
import os

path = '/home/yourusername/mysite'
if path not in sys.path:
    sys.path.append(path)

os.chdir(path)

from app import app as application
```

**Important:** Replace `yourusername` with your actual PythonAnywhere username

---

## Step 6: Install Python Packages

In **Bash Console**, run:
```bash
cd ~/mysite
pip install --user -r requirements.txt
```

---

## Step 7: Create config.json

1. Go to **Files** → `/home/yourusername/mysite/`
2. Create new file: `config.json`
3. Add this content:

```json
{
    "MASTER_PASSWORD": "your_strong_password_here",
    "SECRET_KEY": "your_random_secret_key_here"
}
```

**⚠️ IMPORTANT:**
- Use a STRONG password (20+ characters with numbers, symbols)
- Use a random string for SECRET_KEY
- **Never share this file**
- Better yet, use Environment Variables (see below)

---

## Step 8: Set Environment Variables (Recommended for Production)

In **Web** tab → **Environment variables**:

Add:
```
MASTER_PASSWORD = your_strong_password_here
SECRET_KEY = your_random_secret_key_here
```

This is MORE SECURE than having them in config.json

---

## Step 9: Create Initial Admin User (sysop)

In **Bash Console**:

```bash
cd ~/mysite
mkdir -p users

python3 << 'EOF'
import json
from werkzeug.security import generate_password_hash

# Create the sysop admin user (optional - can use master password)
user_data = {
    "username": "admin_user",
    "password": generate_password_hash("strong_password_here"),
    "is_admin": True
}

with open("users/admin_user.json", "w") as f:
    json.dump(user_data, f, indent=4)

print("Admin user created!")
EOF
```

---

## Step 10: Reload Web App

1. Go to **Web** tab
2. Click **Reload** button at the top
3. Wait 10 seconds
4. Check the green status indicator

---

## Step 11: Visit Your Live Site

1. In **Web** tab, click your domain name
2. Your site is now LIVE!

**Your URL will be:** `https://yourusername.pythonanywhere.com`

---

## Step 12: Create Custom Domain (Optional)

1. Buy a domain (namecheap.com, godaddy.com, etc.)
2. In PythonAnywhere **Web** tab → **Web address**
3. Add custom domain
4. Update domain DNS settings (PythonAnywhere provides instructions)

---

## Troubleshooting

### "ImportError: No module named 'flask'"
```bash
cd ~/mysite
pip install --user -r requirements.txt
```
Then reload web app.

### "404 Not Found" 
Check that WSGI file path is correct (matches your username).

### Files not uploading
Make sure directories exist:
```bash
mkdir -p ~/mysite/{users,uploads,text_entries,static/{images,videos}}
```

### Getting "permission denied"
Files need write permissions:
```bash
chmod 755 ~/mysite/uploads
chmod 755 ~/mysite/text_entries
chmod 755 ~/mysite/users
```

### Can't log in
Check that `config.json` or environment variables have `MASTER_PASSWORD` set.

---

## Important Notes

### For FREE tier:
- ✅ Works great for small projects
- ⚠️ App sleeps after 3 months if inactive
- ⚠️ Limited CPU/disk space
- ⚠️ Shared resources

### For PAID tier ($5-9/month):
- ✅ Always active
- ✅ More storage/CPU
- ✅ Multiple web apps
- ✅ Better performance

---

## Daily Operations

### Backing Up Your Data
1. Go to **Files** tab
2. Download these folders regularly:
   - users/
   - uploads/
   - text_entries/
   - activity_log.json
   - uploads_metadata.json

### Updating Your Code
If using GitHub:
```bash
cd ~/mysite
git pull origin main
pip install --user -r requirements.txt
```
Then reload web app.

### Viewing Logs
In **Web** tab → scroll down to **Log files**
- Server log: Shows errors
- Error log: Shows Python errors

---

## Security Checklist

- [ ] Changed master password to something strong
- [ ] Set SECRET_KEY to random string
- [ ] Removed config.json (use environment variables instead)
- [ ] Created admin user
- [ ] Tested login works
- [ ] Checked that file upload works
- [ ] Verified users can only see media (admin-only areas protected)
- [ ] Added custom domain (optional but recommended)

---

## Your Site is Now Live! 🎉

Share your URL: `https://yourusername.pythonanywhere.com`

Enjoy your media management system!
