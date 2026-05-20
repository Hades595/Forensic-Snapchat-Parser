import os
import shutil
import sqlite3
from datetime import datetime, timezone, timedelta

CONTENT_TYPES = {
    1: 'Chat', 2: 'Snap', 3: 'External Media', 4: 'Sticker',
    5: 'Voice Note', 6: 'Share', 7: 'Location', 8: 'Audio Note',
    9: 'Reaction', 10: 'Story Reply', 11: 'Spotlight', 12: 'Call Log',
}

CONV_TYPES = {1: '1-on-1', 2: 'Group', 3: 'Group'}


def _ms_to_str(ms):
    if not ms:
        return ''
    try:
        dt = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception:
        return str(ms)


def process_arroyo_ios(input_path: str, output_path: str):
    """
    Locate arroyo.db in an iOS extraction, copy it with its WAL, and parse it.
    Returns (conversations, messages).
    """
    arroyo_db = None
    arroyo_wal = None

    for root, dirs, files in os.walk(input_path):
        for fname in files:
            if fname == 'arroyo.db':
                arroyo_db = os.path.join(root, fname)
            if fname == 'arroyo.db-wal':
                arroyo_wal = os.path.join(root, fname)
        if arroyo_db:
            break

    if not arroyo_db:
        print("arroyo.db not found in iOS extraction")
        return [], []

    dest_db = os.path.join(output_path, 'arroyo.db')
    shutil.copy2(arroyo_db, dest_db)
    print("Copied arroyo.db:", dest_db)

    if arroyo_wal and os.path.exists(arroyo_wal):
        shutil.copy2(arroyo_wal, os.path.join(output_path, 'arroyo.db-wal'))
        print("Copied arroyo.db-wal")

    return parse_arroyo_db(dest_db, output_path)


def parse_arroyo_db(db_path: str, output_path: str):
    """
    Parse an arroyo.db (iOS or Android — identical schema).
    Returns (conversations, messages).
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA wal_checkpoint(FULL);")

    conversations = _parse_conversations(conn, output_path)
    messages = _parse_messages(conn, output_path)

    conn.close()
    return conversations, messages


def _parse_conversations(conn, output_path):
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT
                client_conversation_id,
                conversation_title,
                display_timestamp,
                message_type,
                streak_count,
                streak_expiration_timestamp_ms,
                unread_chat_count,
                conversation_type,
                last_chat_sender,
                tombstoned
            FROM feed_entry
            ORDER BY display_timestamp DESC
        """)
        rows = cur.fetchall()
    except Exception as e:
        print("Error reading feed_entry:", e)
        return []

    # Count messages per conversation for the report
    try:
        cur.execute("SELECT client_conversation_id, COUNT(*) FROM conversation_message GROUP BY client_conversation_id")
        msg_counts = dict(cur.fetchall())
    except Exception:
        msg_counts = {}

    conversations = []
    with open(os.path.join(output_path, 'arroyo_conversations.csv'), 'w', encoding='utf-8') as f:
        f.write('conversation_id,title,last_activity,streak,unread,type,last_sender,message_count,deleted\n')
        for row in rows:
            conv_id, title, display_ts, msg_type, streak, streak_exp, unread, conv_type, last_sender, tombstoned = row
            title_str = title or ''
            last_activity = _ms_to_str(display_ts)
            streak_expiry = _ms_to_str(streak_exp) if streak_exp else ''
            conv_type_label = CONV_TYPES.get(conv_type, str(conv_type or ''))
            msg_count = msg_counts.get(conv_id, 0)
            deleted = bool(tombstoned)

            conv = {
                'conversation_id': conv_id or '',
                'title': title_str,
                'last_activity': last_activity,
                'last_activity_ts': int(display_ts) if display_ts else 0,
                'streak': int(streak) if streak else 0,
                'streak_expiry': streak_expiry,
                'unread': int(unread) if unread else 0,
                'conversation_type': conv_type_label,
                'last_sender': last_sender or '',
                'message_count': msg_count,
                'deleted': deleted,
            }
            conversations.append(conv)

            title_csv = f'"{title_str}"' if ',' in title_str else title_str
            f.write(','.join([
                conv_id or '', title_csv, last_activity,
                str(streak or 0), str(unread or 0), conv_type_label,
                last_sender or '', str(msg_count), str(int(deleted))
            ]) + '\n')

    return conversations


def _parse_messages(conn, output_path):
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT
                client_conversation_id,
                client_message_id,
                server_message_id,
                creation_timestamp,
                read_timestamp,
                sender_id,
                content_type,
                is_saved,
                is_viewed_by_user,
                hidden_from_platform
            FROM conversation_message
            ORDER BY creation_timestamp ASC
        """)
        rows = cur.fetchall()
    except Exception as e:
        print("Error reading conversation_message:", e)
        return []

    messages = []
    with open(os.path.join(output_path, 'arroyo_messages.csv'), 'w', encoding='utf-8') as f:
        f.write('conversation_id,message_id,server_message_id,timestamp,read_timestamp,sender_id,content_type,is_saved,is_viewed,deleted\n')
        for row in rows:
            conv_id, client_id, server_id, create_ts, read_ts, sender, ctype, saved, viewed, hidden = row
            timestamp = _ms_to_str(create_ts)
            read_time = _ms_to_str(read_ts) if read_ts else ''
            ctype_label = CONTENT_TYPES.get(ctype, f'Type {ctype}' if ctype else 'Unknown')
            deleted = bool(hidden)

            msg = {
                'conversation_id': conv_id or '',
                'message_id': int(client_id) if client_id else 0,
                'server_message_id': int(server_id) if server_id else 0,
                'timestamp': timestamp,
                'timestamp_ts': int(create_ts) if create_ts else 0,
                'read_timestamp': read_time,
                'sender_id': sender or '',
                'content_type': ctype or 0,
                'content_type_label': ctype_label,
                'is_saved': bool(saved),
                'is_viewed': bool(viewed),
                'deleted': deleted,
            }
            messages.append(msg)

            f.write(','.join([
                conv_id or '', str(client_id or ''), str(server_id or ''),
                timestamp, read_time, sender or '',
                ctype_label, str(int(bool(saved))), str(int(bool(viewed))), str(int(deleted))
            ]) + '\n')

    return messages
