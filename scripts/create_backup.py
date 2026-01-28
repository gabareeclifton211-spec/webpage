import os
import sys
import zipfile
import hashlib
import json
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
EXCLUDE_DIRS = {'.venv', '.git', 'cloned_webpage', '__pycache__'}
EXCLUDE_FILES = {'config.local.json'}

def should_exclude(path, rel):
    # Exclude if any part of rel path is in EXCLUDE_DIRS
    parts = rel.split(os.sep)
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    if os.path.basename(rel) in EXCLUDE_FILES:
        return True
    return False


def make_backup(out_dir=None):
    now = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    if out_dir is None:
        out_dir = ROOT
    os.makedirs(out_dir, exist_ok=True)
    zip_name = os.path.join(out_dir, f'workspace_backup_{now}.zip')
    manifest = []

    with zipfile.ZipFile(zip_name, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            # Compute relative path from ROOT
            rel_dir = os.path.relpath(dirpath, ROOT)
            if rel_dir == '.':
                rel_dir = ''
            # prune excluded dirs
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for fname in filenames:
                rel = os.path.join(rel_dir, fname) if rel_dir else fname
                if should_exclude(os.path.join(dirpath, fname), rel):
                    continue
                full = os.path.join(dirpath, fname)
                arcname = rel.replace('\\', '/')
                zf.write(full, arcname)
                size = os.path.getsize(full)
                manifest.append({'path': arcname, 'size': size})

    # write manifest JSON
    manifest_name = zip_name.replace('.zip', '.manifest.json')
    with open(manifest_name, 'w', encoding='utf-8') as mf:
        json.dump({'created': now, 'root': ROOT, 'excludes_dirs': list(EXCLUDE_DIRS), 'excludes_files': list(EXCLUDE_FILES), 'files': manifest}, mf, indent=2)

    # write sha256 checksum
    sha_name = zip_name + '.sha256'
    h = hashlib.sha256()
    with open(zip_name, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    with open(sha_name, 'w') as s:
        s.write(h.hexdigest())

    return zip_name, manifest_name, sha_name


if __name__ == '__main__':
    out = None
    if len(sys.argv) > 1:
        out = sys.argv[1]
    zipf, manf, sha = make_backup(out)
    print('backup:', zipf)
    print('manifest:', manf)
    print('sha256:', sha)
