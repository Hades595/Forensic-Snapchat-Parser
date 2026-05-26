import os
import re
import sqlite3
from datetime import datetime, timezone

# ── Pattern matchers for SnapUserStore field identification ───────────────────
_EMAIL_RE   = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_PHONE_RE   = re.compile(r'^\+\d{6,}$')
_DATE_RE    = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_LOCALE_RE  = re.compile(r'^[A-Z]{2}$|^[a-z]{2}[-_][A-Z]{2}$')
_NAME_RE    = re.compile(r'^[A-Za-z][A-Za-z\s\'\-\.]{2,}$')
_UUID_STR_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
_NUMERIC_RE = re.compile(r'^[\d_\-]+$')


def _fmt_ms(ms) -> str | None:
    """Convert millisecond epoch timestamp to human-readable UTC string."""
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ms)


def parse_friends(db_path: str) -> list:
    """Parse Friend LEFT JOIN FriendScore from main.db.

    Returns a list of dicts with combined friend and score data.
    """
    query = """
        SELECT
            f._id, f.username, f.userId,
            f.petName, f.displayName, f.serverDisplayName,
            f.friendmojis, f.publicProfilePictureUrl,
            f.addedTimestamp, f.phone,
            f.streakLength, f.streakExpiration,
            f.isOfficial, f.isBrand, f.isPlusSubscriber,
            fs.score AS fs_score, fs.lastUpdateTimestamp
        FROM Friend f
        LEFT JOIN FriendScore fs ON fs.friendRowId = f._id
        ORDER BY f.username COLLATE NOCASE
    """
    friends = []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        conn.close()
    except Exception:
        return friends

    for row in rows:
        (row_id, username, user_id,
         pet_name, display_name, server_display_name,
         friendmojis, profile_pic_url,
         added_ts, phone,
         streak_length, streak_expiration,
         is_official, is_brand, is_plus,
         fs_score, fs_updated_ts) = row

        resolved_name = pet_name or display_name or server_display_name or username or user_id or ""

        friends.append({
            "username":        username or "",
            "user_id":         user_id or "",
            "display_name":    resolved_name,
            "friendmojis":     friendmojis or None,
            "profile_pic_url": profile_pic_url or None,
            "score":           fs_score,
            "score_updated":   _fmt_ms(fs_updated_ts),
            "added":           _fmt_ms(added_ts),
            "streak":          streak_length if streak_length else None,
            "streak_expires":  _fmt_ms(streak_expiration) if streak_expiration else None,
            "phone":           phone or None,
            "is_official":     bool(is_official),
            "is_brand":        bool(is_brand),
            "is_plus":         bool(is_plus),
        })

    return friends


def parse_snap_records(db_path: str) -> list:
    """Parse Snap table from main.db.

    Returns a list of dicts with snap record metadata, sorted newest first.
    """
    query = """
        SELECT snapId, timestamp, mediaId, mediaIv, mediaKey,
               snapType, mediaUrl, durationInMs, groupType, storyRowId,
               isInfiniteDuration, attachmentUrl
        FROM Snap
        ORDER BY timestamp DESC
    """
    records = []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        conn.close()
    except Exception:
        return records

    for row in rows:
        (snap_id, timestamp, media_id, media_iv, media_key,
         snap_type, media_url, duration_ms, group_type, story_row_id,
         is_infinite, attachment_url) = row

        duration_s = None
        if duration_ms is not None and not is_infinite:
            try:
                duration_s = round(duration_ms / 1000.0, 1)
            except Exception:
                pass

        records.append({
            "snap_id":        snap_id or "",
            "timestamp":      _fmt_ms(timestamp),
            "timestamp_ms":   timestamp or 0,
            "media_id":       media_id or None,
            "media_iv":       media_iv or None,
            "media_key":      media_key or None,
            "snap_type":      snap_type,
            "media_url":      media_url or None,
            "duration_s":     duration_s,
            "is_infinite":    bool(is_infinite),
            "group_type":     group_type or None,
            "story_row_id":   story_row_id,
            "attachment_url": attachment_url or None,
        })

    return records


def parse_stories(db_path: str) -> list:
    """Parse Story table from main.db.

    Returns a list of dicts with story metadata, sorted newest first.
    """
    query = """
        SELECT storyId, userName, displayName, userId, profileDescription,
               latestTimeStamp, latestExpirationTimestamp,
               viewed, kind, groupStoryType, isPostable
        FROM Story
        ORDER BY latestTimeStamp DESC
    """
    stories = []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        conn.close()
    except Exception:
        return stories

    for row in rows:
        (story_id, username, display_name, user_id, description,
         latest_ts, expiry_ts,
         viewed, kind, group_story_type, is_postable) = row

        stories.append({
            "story_id":        story_id or "",
            "username":        username or None,
            "display_name":    display_name or None,
            "user_id":         user_id or None,
            "description":     description or None,
            "latest":          _fmt_ms(latest_ts),
            "expires":         _fmt_ms(expiry_ts),
            "viewed":          bool(viewed),
            "kind":            kind,
            "group_story_type": group_story_type,
            "is_postable":     bool(is_postable) if is_postable is not None else None,
        })

    return stories


def find_core_db_android(input_path: str) -> str | None:
    """Walk input_path and return the first core.db found inside a databases/ directory."""
    for root, _, files in os.walk(input_path):
        if "core.db" in files and "databases" in root:
            return os.path.join(root, "core.db")
    return None


def parse_user_profile(db_path: str) -> dict:
    """Parse SnapUserStore key-value store from core.db.

    The table stores each profile field as a separate row with a binary itemKey.
    Field identity is inferred by pattern-matching the textVal content.

    Returns a dict with keys: username, full_name, dob, email, phone, locale.
    All values are str or None.
    """
    profile = {
        "username":  None,
        "full_name": None,
        "dob":       None,
        "email":     None,
        "phone":     None,
        "locale":    None,
        "user_id":   None,
    }
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # Extract the user UUID embedded in the CoreData groupKey (e.g. "CoreData\t{uuid}\t")
        cur.execute("SELECT DISTINCT groupKey FROM SnapUserStore WHERE groupKey LIKE 'CoreData%' LIMIT 1")
        gk_row = cur.fetchone()
        if gk_row:
            match = _UUID_STR_RE.search(gk_row[0])
            if match:
                profile["user_id"] = match.group(0)
        cur.execute("""
            SELECT textVal FROM SnapUserStore
            WHERE groupKey LIKE 'CoreData%'
              AND textVal IS NOT NULL AND textVal != ''
            ORDER BY _id
        """)
        texts = [row[0] for row in cur.fetchall()]
        conn.close()
    except Exception:
        return profile

    for text in texts:
        t = text.strip()
        if not t or len(t) > 120 or _NUMERIC_RE.match(t) or _UUID_STR_RE.match(t):
            continue
        if _EMAIL_RE.match(t) and not profile["email"]:
            profile["email"] = t
        elif _PHONE_RE.match(t) and not profile["phone"]:
            profile["phone"] = t
        elif _DATE_RE.match(t) and not profile["dob"]:
            profile["dob"] = t
        elif _LOCALE_RE.match(t) and not profile["locale"]:
            profile["locale"] = t
        elif ' ' in t and _NAME_RE.match(t) and not profile["full_name"]:
            profile["full_name"] = t
        elif ' ' not in t and not profile["username"] and len(t) >= 3:
            profile["username"] = t

    return profile
