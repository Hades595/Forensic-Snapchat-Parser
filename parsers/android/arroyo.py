import os
import shutil
import sqlite3
from datetime import datetime, timezone

from parsers.ios.arroyo import parse_arroyo_db, _ms_to_str

FRIEND_LINK_TYPES = {0: 'Mutual', 1: 'Added by me', 2: 'Added me'}


def process_arroyo_android(input_path: str, output_path: str):
    """
    Locate and parse arroyo.db and main.db from an Android extraction.
    Returns (conversations, messages, friends).
    """
    arroyo_db = None
    arroyo_wal = None
    main_db = None

    for root, dirs, files in os.walk(input_path):
        for fname in files:
            if fname == 'arroyo.db':
                arroyo_db = os.path.join(root, fname)
            if fname == 'arroyo.db-wal':
                arroyo_wal = os.path.join(root, fname)
            if fname == 'main.db':
                main_db = os.path.join(root, fname)

    conversations, messages = [], []
    if arroyo_db:
        dest = os.path.join(output_path, 'arroyo.db')
        shutil.copy2(arroyo_db, dest)
        print("Copied arroyo.db:", dest)
        if arroyo_wal and os.path.exists(arroyo_wal):
            shutil.copy2(arroyo_wal, os.path.join(output_path, 'arroyo.db-wal'))
        conversations, messages = parse_arroyo_db(dest, output_path)
    else:
        print("arroyo.db not found in Android extraction")

    friends = []
    if main_db:
        dest_main = os.path.join(output_path, 'main.db')
        shutil.copy2(main_db, dest_main)
        print("Copied main.db:", dest_main)
        friends = _parse_main_db(dest_main, output_path)
    else:
        print("main.db not found in Android extraction")

    return conversations, messages, friends


def _parse_main_db(db_path: str, output_path: str):
    conn = sqlite3.connect(db_path)
    friends = _parse_friends(conn, output_path)
    _parse_stories(conn, output_path)
    conn.close()
    return friends


def _parse_friends(conn, output_path):
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT
                username,
                displayName,
                userId,
                score,
                birthday,
                sentToMe,
                receivedFromMe,
                addedTimestamp,
                reverseAddedTimestamp,
                streakLength,
                streakExpiration,
                friendLinkType
            FROM Friend
            ORDER BY addedTimestamp ASC
        """)
        rows = cur.fetchall()
    except Exception as e:
        print("Error reading Friend table:", e)
        return []

    friends = []
    with open(os.path.join(output_path, 'friends.csv'), 'w', encoding='utf-8') as f:
        f.write('username,display_name,user_id,snap_score,birthday,snaps_received,snaps_sent,added_date,added_me_date,streak,streak_expiry,relationship\n')
        for row in rows:
            (username, display_name, user_id, score, birthday_ts,
             sent_to_me, received_from_me, added_ts, reverse_added_ts,
             streak, streak_exp, link_type) = row

            birthday = _ms_to_str(birthday_ts) if birthday_ts else ''
            added = _ms_to_str(added_ts) if added_ts else ''
            added_me = _ms_to_str(reverse_added_ts) if reverse_added_ts else ''
            streak_expiry = _ms_to_str(streak_exp) if streak_exp else ''
            relationship = FRIEND_LINK_TYPES.get(link_type, str(link_type or ''))

            friend = {
                'username': username or '',
                'display_name': display_name or '',
                'user_id': user_id or '',
                'snap_score': int(score) if score else 0,
                'birthday': birthday,
                'snaps_received': int(sent_to_me) if sent_to_me else 0,
                'snaps_sent': int(received_from_me) if received_from_me else 0,
                'added_date': added,
                'added_me_date': added_me,
                'streak': int(streak) if streak else 0,
                'streak_expiry': streak_expiry,
                'relationship': relationship,
            }
            friends.append(friend)

            dn_csv = f'"{display_name}"' if display_name and ',' in display_name else (display_name or '')
            f.write(','.join([
                username or '', dn_csv, user_id or '',
                str(score or 0), birthday,
                str(sent_to_me or 0), str(received_from_me or 0),
                added, added_me,
                str(streak or 0), streak_expiry, relationship
            ]) + '\n')

    return friends


def _parse_stories(conn, output_path):
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT
                username,
                displayName,
                captionTextDisplay,
                canonicalDisplayTime,
                expirationTimestamp,
                viewed,
                friendScreenshotCount,
                friendViewCount,
                thumbnailUrl
            FROM StorySnap
            ORDER BY canonicalDisplayTime DESC
        """)
        rows = cur.fetchall()
    except Exception as e:
        print("StorySnap table not available:", e)
        return

    with open(os.path.join(output_path, 'stories.csv'), 'w', encoding='utf-8') as f:
        f.write('username,display_name,caption,posted_time,expiration,viewed,screenshot_count,view_count,thumbnail_url\n')
        for row in rows:
            username, display_name, caption, post_ts, exp_ts, viewed, screenshots, views, thumb = row
            posted = _ms_to_str(post_ts)
            expiry = _ms_to_str(exp_ts) if exp_ts else ''
            caption_safe = f'"{caption}"' if caption and ',' in caption else (caption or '')
            f.write(','.join([
                username or '', display_name or '', caption_safe, posted, expiry,
                str(int(bool(viewed))), str(screenshots or 0), str(views or 0), thumb or ''
            ]) + '\n')
