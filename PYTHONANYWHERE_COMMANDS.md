# PythonAnywhere Deployment - Step-by-Step Commands

## Your Deployment Checklist

- [ ] Created GitHub account
- [ ] Pushed code to GitHub (see GITHUB_SETUP.md)
- [ ] Created PythonAnywhere account
- [ ] Completed steps below
- [ ] Your site is LIVE!

---

## ⏱️ Total Time: ~15 minutes

---

## STEP 1: Create PythonAnywhere Account

**Do this manually:**
1. Go to **pythonanywhere.com**
2. Click "Start exploring PythonAnywhere"
3. Sign up FREE account
4. **Verify your email**
5. Log in

---

## STEP 2: Set Up Bash Console & Clone Your Repo

**In PythonAnywhere:**
1. Click **Consoles** (top menu)
2. Click **Bash**
3. Wait for console to load

**Copy & paste these commands one at a time:**

```bash
cd ~
```

```bash
git clone https://github.com/YOUR_USERNAME/webpage.git mysite
```

**⚠️ IMPORTANT:** Replace `YOUR_USERNAME` with your actual GitHub username!

Wait for it to finish (should say "done").

---

## STEP 3: Install Python Packages

**In the same Bash console, run:**

```bash
cd ~/mysite
pip install --user -r requirements.txt
```

This will install Flask and required packages. Wait for completion.

---

## STEP 4: Create Required Directories

**Still in Bash console:**

```bash
mkdir -p users uploads text_entries
mkdir -p static/images static/videos
mkdir -p uploads/images uploads/videos uploads/text
```

---

## STEP 5: Create config.json File

**In Bash console:**

```bash
cat > ~/mysite/config.json << 'EOF'
{
    "MASTER_PASSWORD": "ChangeMe123!@#NewPassword",
    "SECRET_KEY": "your_random_secret_key_12345_change_this"
}
EOF
```

**⚠️ IMPORTANT:**
- Replace `ChangeMe123!@#NewPassword` with YOUR strong password (20+ chars)
- Replace `your_random_secret_key_12345_change_this` with random string
- **NEVER share this file**

Verify it was created:
```bash
cat ~/mysite/config.json
```

---

## STEP 6: Set Up Web App in PythonAnywhere

**Do this manually:**
1. Click **Web** (top menu)
2. Click **Add a new web app**
3. When asked, choose:
   - **Manual configuration**
   - **Python 3.10** (or latest available)
4. Click through to finish

---

## STEP 7: Create WSGI Configuration File

**In the Web tab, you should see:**
- Your domain: `yourusername.pythonanywhere.com`
- Below it: "WSGI configuration file" with a file path

**Click on that file path** (it opens in editor)

**Delete ALL content** and replace with this (update username):

```python
import sys
import os

# Add your project to path
path = '/home/yourusername/mysite'
if path not in sys.path:
    sys.path.append(path)

os.chdir(path)

# Import your Flask app
from app import app as application
```

**CRITICAL:** Replace `yourusername` with your PythonAnywhere username!

**Example:** If your domain is `alice.pythonanywhere.com`, use `alice`

Click **Save** (Ctrl+S)

---

## STEP 8: Reload Web App

**In Web tab:**
1. Scroll to top
2. Click green **Reload** button
3. Wait ~10 seconds
4. Should show green circle ✅ with "Running"

---

## STEP 9: Test Your Site

**Your site is now LIVE!**

1. In Web tab, click your domain name: `https://yourusername.pythonanywhere.com`
2. Should see your **home page**
3. Try to **login** with master password

**Testing Logins:**
- Username: anything (e.g., `testuser`)
- Password: Your master password (from config.json)

Should redirect to home page!

---

## STEP 10: Create First Admin User (Optional)

**In Bash console:**

```bash
cd ~/mysite
python3 << 'EOF'
import json
import os
from werkzeug.security import generate_password_hash

# Create admin user
os.makedirs('users', exist_ok=True)
user_data = {
    "username": "admin",
    "password": generate_password_hash("your_admin_password_123"),
    "is_admin": True
}

with open('users/admin.json', 'w') as f:
    json.dump(user_data, f, indent=4)

print("✅ Admin user created!")
print("Login as: admin / your_admin_password_123")
EOF
```

---

## STEP 11: Test All Features

**On your live site:**

1. **Login** with master password
2. **Media Gallery** - should be empty initially
3. **Text Entries** - should be empty
4. **Upload Files** - try uploading an image
5. **Admin Dashboard** - check storage stats
6. **Check activity log** - should show your actions

---

## STEP 12: Get Your Custom Domain (Optional)

**If you want:** `mycoolsite.com` instead of `yourusername.pythonanywhere.com`

1. Buy a domain (namecheap.com - $10/year)
2. In PythonAnywhere Web tab → scroll to **Web address**
3. Add your custom domain
4. Update domain's DNS settings (PythonAnywhere shows how)

---

## 🎉 Congratulations! Your Site is LIVE!

Your public URL: `https://yourusername.pythonanywhere.com`

Share it with friends!

---

## Common Issues & Fixes

### ❌ "502 Bad Gateway" or "Error"

**Solution:**
1. Go to Web tab → scroll down → **Error log**
2. Check what error is shown
3. Most common: Wrong username in WSGI file

Fix WSGI file and reload:
```bash
# In Bash, verify correct path
ls -la /home/yourusername/mysite/
```

### ❌ "Module not found" error

**Solution:**
```bash
cd ~/mysite
pip install --user -r requirements.txt
```
Then reload web app.

### ❌ Can't login with master password

**Check config.json:**
```bash
cat ~/mysite/config.json
```

Make sure MASTER_PASSWORD is set.

### ❌ Can't upload files

Check permissions:
```bash
chmod 755 ~/mysite/uploads
chmod 755 ~/mysite/users
chmod 755 ~/mysite/text_entries
```

---

## Updating Your Code

After making changes locally:

```bash
# On your computer
git add .
git commit -m "Your changes"
git push
```

On PythonAnywhere:
```bash
cd ~/mysite
git pull origin main
```

Then reload web app in PythonAnywhere.

---

## Backing Up Your Data

**Download these regularly:**
1. In Files tab
2. Download: `uploads/`, `users/`, `activity_log.json`
3. Store in safe place (Dropbox, Google Drive, etc.)

---

## Monitoring Your Site

**Check status anytime:**
1. Go to Web tab
2. If ✅ green = running
3. If ⚠️ yellow/red = issue (check error log)

**View logs:**
- Web tab → scroll down → Log files
- Server log = requests
- Error log = Python errors

---

## You're All Set! 🚀

Your media gallery is live and accessible to the world!

Need help? Check the error logs or email support@pythonanywhere.com
