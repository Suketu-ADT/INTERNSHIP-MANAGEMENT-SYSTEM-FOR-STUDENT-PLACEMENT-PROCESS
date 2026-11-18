import os
import uuid
from datetime import datetime


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def unique_filename(original_filename):
    ext = original_filename.rsplit(".", 1)[1].lower() if "." in original_filename else ""
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    token = uuid.uuid4().hex[:8]
    return f"{stamp}_{token}.{ext}" if ext else f"{stamp}_{token}"


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def time_ago(dt):
    if not dt:
        return ""
    diff = datetime.utcnow() - dt
    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours}h ago"
    days = int(hours // 24)
    if days < 30:
        return f"{days}d ago"
    months = int(days // 30)
    return f"{months}mo ago"
