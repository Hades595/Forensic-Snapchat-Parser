import os
import re
import sqlite3
from datetime import datetime, timezone

CONTENT_TYPE_LABELS = {
    0:  "Overlay Text",
    1:  "Chat",
    2:  "Snap",
    3:  "External Media",
    4:  "Story Reply",
    5:  "Note",
    6:  "Status",
    7:  "Location",
}

ARROYO_QUERY = """
SELECT
    cm.client_conversation_id,
    cm.client_message_id,
    cm.server_message_id,
    cm.sender_id,
    cm.creation_timestamp,
    cm.read_timestamp,
    cm.content_type,
    cm.message_state_type,
    cm.is_saved,
    cm.is_viewed_by_user,
    cm.message_content
FROM conversation_message cm
ORDER BY cm.client_conversation_id, cm.creation_timestamp DESC
"""

# ── Noise filters applied to extracted proto strings ──────────────────────────
_BASE64_RE    = re.compile(r'^[A-Za-z0-9+/]{20,}={0,2}$')
_HEXCOL_RE    = re.compile(r'^[0-9A-Fa-f]{6,8}$')
_UUID_RE      = re.compile(r'^\$?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
_MEDIA_ID_RE  = re.compile(r'^[A-Za-z0-9_-]{15,}$')   # Snapchat media / snap keys (no spaces, ≥15 chars)
_NUMBER_RE    = re.compile(r'^-?\d+(\.\d+)?$')          # bare integers / decimals
_FONT_NAME_RE = re.compile(r'^[A-Z][A-Za-z0-9]+(?:-[A-Za-z][A-Za-z0-9]*)*$')  # CamelCase identifiers

# Known short Snapchat font / style names that are too short to catch with the length filter
_KNOWN_FONT_NAMES = {
    "Classic", "ClassicB", "Elegant", "Helvetica", "SystemDefault",
    "Default", "Sans", "Serif", "Bold", "Italic",
}


def _is_noise(s: str) -> bool:
    s = s.strip()
    if len(s) < 3:
        return True
    # Must contain at least 2 plain ASCII letters to rule out binary garbage
    if sum(1 for c in s if c.isalpha() and ord(c) < 128) < 2:
        return True
    if _BASE64_RE.match(s):       # encryption keys
        return True
    if _HEXCOL_RE.match(s):       # hex colour codes (FFFFFFFF, etc.)
        return True
    if s.startswith("http"):      # CDN / download URLs
        return True
    if _UUID_RE.match(s):         # UUIDs (with or without leading $)
        return True
    if _NUMBER_RE.match(s):       # bare integers / floats like -1, 0
        return True
    if _MEDIA_ID_RE.match(s):     # Snapchat media keys (no spaces, long alphanumeric+_-)
        return True
    if s in _KNOWN_FONT_NAMES:    # known short Snapchat font / style names
        return True
    # CamelCase identifier with no spaces and length > 7 → likely a font / style name
    if " " not in s and len(s) > 7 and _FONT_NAME_RE.match(s):
        return True
    return False


# ── Minimal protobuf varint decoder ───────────────────────────────────────────

def _read_varint(data: bytes, pos: int):
    result = shift = 0
    while pos < len(data):
        b = data[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def _extract_strings(data: bytes, depth: int = 0, max_depth: int = 10) -> list:
    """Recursively walk protobuf bytes and collect valid UTF-8 string fields."""
    results = []
    i = 0
    data = bytes(data)
    while i < len(data):
        try:
            tag, i = _read_varint(data, i)
            wire = tag & 0x7
            if wire == 0:                           # varint — skip
                _, i = _read_varint(data, i)
            elif wire == 1:                         # 64-bit — skip
                i += 8
            elif wire == 2:                         # length-delimited
                length, i = _read_varint(data, i)
                if length < 0 or i + length > len(data):
                    break
                chunk = data[i:i + length]
                try:
                    s = chunk.decode("utf-8")
                    if len(s) >= 2 and all(c.isprintable() or c in "\n\r\t" for c in s):
                        results.append(s)
                except Exception:
                    pass
                if depth < max_depth and 2 < length < 8192:
                    results.extend(_extract_strings(chunk, depth + 1, max_depth))
                i += length
            elif wire == 5:                         # 32-bit — skip
                i += 4
            else:
                break
        except Exception:
            break
    return results


def _decode_message_content(blob) -> str | None:
    """Extract human-readable text from a message_content protobuf blob."""
    if not blob:
        return None
    try:
        raw_strings = _extract_strings(bytes(blob))
    except Exception:
        return None

    seen = set()
    texts = []
    for s in raw_strings:
        s = s.strip()
        if s and not _is_noise(s) and s not in seen:
            seen.add(s)
            texts.append(s)

    return " | ".join(texts) if texts else None


# ── Timestamp helper ──────────────────────────────────────────────────────────

def _format_ts(ms) -> str | None:
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ms)


# ── Public API ────────────────────────────────────────────────────────────────

def find_arroyo(input_path: str) -> str | None:
    """Walk input_path and return the first arroyo.db path found."""
    for root, _, files in os.walk(input_path):
        if "arroyo.db" in files:
            return os.path.join(root, "arroyo.db")
    return None


def find_names_db_android(input_path: str) -> str | None:
    """Walk input_path and return the first main.db found inside a databases/ directory."""
    for root, _, files in os.walk(input_path):
        if "main.db" in files and "databases" in root:
            return os.path.join(root, "main.db")
    return None


def find_names_db_ios(input_path: str) -> str | None:
    """Walk input_path and return the first friending_notification_snapchatter.db found."""
    for root, _, files in os.walk(input_path):
        if "friending_notification_snapchatter.db" in files:
            return os.path.join(root, "friending_notification_snapchatter.db")
    return None


def load_names_android(db_path: str) -> dict:
    """Return {userId: display_name} from main.db Friend table.

    Priority: petName → displayName → serverDisplayName → username → userId
    """
    names = {}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT userId, petName, displayName, serverDisplayName, username FROM Friend"
        )
        for row in cur.fetchall():
            user_id, pet_name, display_name, server_display_name, username = row
            name = pet_name or display_name or server_display_name or username or user_id
            if user_id and name:
                names[user_id] = name
        conn.close()
    except Exception:
        pass
    return names


def load_names_ios(db_path: str) -> dict:
    """Return {userId: display_name} from friending_notification_snapchatter table.

    Priority: displayName → mutableName → userId
    """
    names = {}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT userId, displayName, mutableName FROM friending_notification_snapchatter"
        )
        for row in cur.fetchall():
            user_id, display_name, mutable_name = row
            name = display_name or mutable_name or user_id
            if user_id and name:
                names[user_id] = name
        conn.close()
    except Exception:
        pass
    return names


def parse_arroyo(db_path: str, names: dict = None, log_callback=None) -> list:
    """Query conversation_message in arroyo.db and return a list of chat dicts."""
    def _log(msg, lvl="INFO"):
        if log_callback:
            log_callback(msg, lvl)
        else:
            print(msg)

    chats = []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(ARROYO_QUERY)
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        _log(f"Failed to query arroyo.db: {e}", "ERROR")
        return chats

    for row in rows:
        (conv_id, msg_id, server_id, sender_id,
         creation_ts, read_ts, content_type_int,
         state, is_saved, is_viewed, message_blob) = row

        content_type = CONTENT_TYPE_LABELS.get(content_type_int, f"Type {content_type_int}")
        sender_id_str = sender_id or ""

        chats.append({
            "conversation_id":  conv_id or "",
            "message_id":       msg_id,
            "server_id":        server_id,
            "sender_id":        sender_id_str,
            "sender_name":      names.get(sender_id_str) if names and sender_id_str else None,
            "timestamp":        _format_ts(creation_ts),
            "timestamp_ms":     creation_ts or 0,
            "read_timestamp":   _format_ts(read_ts),
            "content_type":     content_type,
            "message_content":  _decode_message_content(message_blob),
            "state":            state or "",
            "is_saved":         bool(is_saved),
            "is_viewed":        bool(is_viewed),
        })

    _log(f"Parsed {len(chats)} messages from arroyo.db", "OK")
    return chats
