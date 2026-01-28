# Git & GitHub Setup Guide

## Step 1: Create GitHub Account (if you don't have one)

1. Go to **github.com**
2. Click **Sign up**
3. Create account with email
4. Verify email

---

## Step 2: Create New GitHub Repository

1. Log in to GitHub
2. Click **+** icon (top right) → **New repository**
3. Repository name: `webpage` (or `media-gallery`)
4. Description: "Flask Media Gallery Management System"
5. Choose **Private** (so only you can see it)
6. **DO NOT** initialize with README (we have our own)
7. Click **Create repository**

After creation, GitHub shows a page with commands. Copy the HTTPS URL for later.

---

## Step 3: Initialize Git Locally

Open **PowerShell** in your project folder and run these commands:

### Navigate to your project:
```powershell
cd "C:\Users\deada\OneDrive\Desktop\webpage"
```

### Initialize git repository:
```powershell
git init
```

### Add your GitHub repository (REPLACE with your URL):
```powershell
git remote add origin https://github.com/YOUR_USERNAME/webpage.git
```

### Add all files:
```powershell
git add .
```

### Create first commit:
```powershell
git commit -m "Initial commit: Flask media gallery with admin dashboard"
```

### Push to GitHub:
```powershell
git branch -M main
git push -u origin main
```

**First time?** It will ask for your GitHub credentials. Use:
- Username: Your GitHub username
- Password: Your GitHub Personal Access Token (see below)

---

## Step 4: Create GitHub Personal Access Token

This is safer than your password:

1. Go to GitHub → Settings (click profile pic, top right)
2. Scroll left sidebar → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. Click **Generate new token (classic)**
4. Name it: `PythonAnywhere`
5. Check these boxes:
   - ✅ repo (all)
   - ✅ write:packages
6. Click **Generate token**
7. **Copy the token** (you won't see it again!)
8. Use this token as your "password" when pushing to GitHub

---

## Step 5: Verify It's on GitHub

1. Go to your GitHub repo
2. You should see all your files there:
   - app.py
   - templates/
   - static/
   - requirements.txt
   - .gitignore
   - DEPLOYMENT_GUIDE.md
   - etc.

**Great!** Your code is backed up and ready!

---

## Step 6: Making Future Updates

After you make changes locally:

```powershell
cd "C:\Users\deada\OneDrive\Desktop\webpage"
git add .
git commit -m "Describe your changes here"
git push
```

On PythonAnywhere, pull the changes:
```bash
cd ~/mysite
git pull origin main
pip install --user -r requirements.txt
```
Then reload your web app.

---

## Troubleshooting Git

### "fatal: not a git repository"
Make sure you're in the correct folder:
```powershell
cd "C:\Users\deada\OneDrive\Desktop\webpage"
git status
```

### "permission denied" when pushing
You might need to:
1. Use Personal Access Token (not password)
2. Or set git credentials:
```powershell
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

### "refusing to merge unrelated histories"
On first push, use:
```powershell
git push -u origin main --force
```

---

## Files to Keep Secret (Already in .gitignore)

These won't be pushed to GitHub:
- ❌ config.json (has master password)
- ❌ activity_log.json
- ❌ uploads_metadata.json
- ❌ users/ folder (user data)
- ❌ uploads/ folder (user files)
- ❌ .env files

---

## Your GitHub Repo is Ready! ✅

Now proceed to: **PYTHONANYWHERE_COMMANDS.md**
