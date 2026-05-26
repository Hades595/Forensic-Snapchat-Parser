import sqlite3
from datetime import datetime, timezone

# Apple absolute time epoch offset (seconds from Unix epoch to 2001-01-01)
_APPLE_EPOCH_OFFSET = 978307200


def _fmt_apple_ts(ts) -> str | None:
    """Convert Apple absolute time (seconds since 2001-01-01) to a UTC string.

    Falls back gracefully if the value is already a Unix timestamp (> 1e10)
    or milliseconds (> 1e12).
    """
    if ts is None:
        return None
    try:
        val = float(ts)
        if val > 1e12:          # milliseconds since Unix epoch
            val /= 1000.0
        elif val < 1e9:         # Apple absolute time — add offset
            val += _APPLE_EPOCH_OFFSET
        return datetime.fromtimestamp(val, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


def parse_friends_ios(db_path: str) -> list:
    """Parse friending_notification_snapchatter.db into a friend list.

    Returns a list of dicts using the same schema as parse_friends() on Android
    so the shared HTML template can render both without changes.
    """
    query = """
        SELECT userId, mutableName, displayName,
               isFromMyContact, notificationType, suggestReason,
               incomingFriendInfoAddedByFriendTs, incomingFriendInfoFriendType
        FROM friending_notification_snapchatter
        ORDER BY displayName COLLATE NOCASE
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
        (user_id, mutable_name, display_name,
         is_from_contact, notification_type, suggest_reason,
         added_ts, friend_type) = row

        resolved_name = display_name or mutable_name or user_id or ""

        friends.append({
            "username":        mutable_name or None,
            "user_id":         user_id or "",
            "display_name":    resolved_name,
            "friendmojis":     None,
            "profile_pic_url": None,
            "score":           None,
            "score_updated":   None,
            "added":           _fmt_apple_ts(added_ts),
            "streak":          None,
            "streak_expires":  None,
            "phone":           None,
            "is_official":     False,
            "is_brand":        False,
            "is_plus":         False,
        })

    return friends


def parse_user_profile_ios(scdb_path: str) -> dict:
    """Extract available account identifiers from scdb ZGALLERYPROFILE.

    iOS does not store username/email/phone in plaintext SQLite databases.
    Only the internal user UUID is reliably available here.
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
        conn = sqlite3.connect(scdb_path)
        cur = conn.cursor()
        cur.execute("SELECT ZUSERID FROM ZGALLERYPROFILE LIMIT 1")
        row = cur.fetchone()
        if row:
            profile["user_id"] = row[0]
        conn.close()
    except Exception:
        pass
    return profile
