import os
import shutil
import sqlite3
import base64
import wget
from datetime import datetime, timezone
from Crypto.Cipher import AES
from parsers.android.reporting import generate_report
from parsers.chats.arroyo import (
    find_arroyo, parse_arroyo, load_conversation_titles,
    find_names_db_android, load_names_android, load_contacts_android,
)
from parsers.android.main_db import (
    parse_friends, parse_snap_records, parse_stories,
    find_core_db_android, parse_user_profile,
)
from parsers.date_filter import snap_in_date_range


def process_android(
    case_name: str,
    input_path: str,
    output_path: str,
    download_files: bool,
    examiner: str = "",
    date_from: str = None,
    date_to: str = None,
    log_callback=None,
) -> str:

    def _log(msg, lvl="INFO"):
        if log_callback:
            log_callback(msg, lvl)
        else:
            print(msg)

    memories_found = None

    for root, dirs, files in os.walk(input_path):
        for file in files:
            if file.startswith("memories") and file.endswith(".db"):
                memories_found = os.path.join(root, file)
        if memories_found:
            break

    _log(f"memories Path: {memories_found}")

    if not memories_found:
        return "memories.db database not found"

    case_folder = os.path.join(output_path, case_name)
    os.makedirs(case_folder, exist_ok=True)
    _log(f"Case folder: {case_folder}")

    memories_dest = os.path.join(case_folder, os.path.basename(memories_found))
    shutil.copy2(memories_found, memories_dest)

    memories_wal = memories_found + "-wal"
    if os.path.exists(memories_wal):
        shutil.copy2(memories_wal, os.path.join(case_folder, os.path.basename(memories_wal)))
        _log(f"Copied memories WAL: {memories_wal}")

    snaps = parse_main(
        memories_path=memories_dest,
        output_path=case_folder,
        download_files=download_files,
        date_from=date_from,
        date_to=date_to,
        log_callback=_log,
    )

    # Build snap_id → snap dict for cross-referencing with arroyo Snap messages
    snap_lookup = {s["snap_id"]: s for s in snaps if s.get("snap_id")}

    # core.db — account profile
    user_profile = {}
    core_src = find_core_db_android(input_path)
    if core_src:
        core_dest = os.path.join(case_folder, "core.db")
        shutil.copy2(core_src, core_dest)
        _log(f"core.db copied: {core_dest}")
        user_profile = parse_user_profile(core_dest)
        _log(f"User profile: {user_profile.get('username') or '(unknown)'}")
    else:
        _log("core.db not found — User tab will be empty", "INFO")

    arroyo_src = find_arroyo(input_path)
    chats = []
    chat_sources = []
    conv_titles = {}
    friends = []
    snap_records = []
    stories = []
    if arroyo_src:
        arroyo_dest = os.path.join(case_folder, "arroyo.db")
        shutil.copy2(arroyo_src, arroyo_dest)
        _log(f"arroyo.db copied: {arroyo_dest}")
        arroyo_wal_src = arroyo_src + "-wal"
        if os.path.exists(arroyo_wal_src):
            shutil.copy2(arroyo_wal_src, arroyo_dest + "-wal")
            _log("arroyo.db-wal copied")
        chat_sources.append("arroyo.db")
        conv_titles = load_conversation_titles(arroyo_dest)
        _log(f"Loaded {len(conv_titles)} conversation entries from feed_entry")
        names_src = find_names_db_android(input_path)
        names = {}
        contacts = {}
        if names_src:
            names_dest = os.path.join(case_folder, "main.db")
            shutil.copy2(names_src, names_dest)
            _log(f"main.db copied: {names_dest}")
            names = load_names_android(names_dest)
            contacts = load_contacts_android(names_dest)
            friends = parse_friends(names_dest)
            snap_records = parse_snap_records(names_dest)
            stories = parse_stories(names_dest)
            _log(f"main.db: {len(friends)} friends, {len(snap_records)} snap records, {len(stories)} stories")
            chat_sources.append("main.db")
        chats = parse_arroyo(arroyo_dest, snap_lookup=snap_lookup, names=names, contacts=contacts, log_callback=_log)

        # Populate sent_to on matched snaps (snap_lookup shares refs with snaps list)
        conv_participants: dict = {}
        for msg in chats:
            cid = msg["conversation_id"]
            label = msg.get("sender_name") or msg.get("sender_id") or ""
            if label and label not in conv_participants.get(cid, []):
                conv_participants.setdefault(cid, []).append(label)
        for msg in chats:
            sid = msg.get("snap_id_ref")
            if sid and sid in snap_lookup and "sent_to" not in snap_lookup[sid]:
                snap_lookup[sid]["sent_to"] = {
                    "conversation_id": msg["conversation_id"],
                    "participants":    conv_participants.get(msg["conversation_id"], []),
                    "sent_at":         msg["timestamp"],
                }
    else:
        _log("arroyo.db not found — chats tab will be empty", "INFO")

    snap_sources = [os.path.basename(memories_dest)]
    report_path = generate_report(
        case_name, snaps, chats, snap_sources, chat_sources, case_folder, examiner,
        friends=friends, snap_records=snap_records, stories=stories,
        user_profile=user_profile, conv_titles=conv_titles,
    )
    _log(f"Report generated: {report_path}", "OK")
    return report_path


def parse_main(memories_path, output_path, download_files, date_from=None, date_to=None, log_callback=None) -> list:

    def _log(msg, lvl="INFO"):
        if log_callback:
            log_callback(msg, lvl)
        else:
            print(msg)

    query = """SELECT
    memories_media._id AS media_id,
    memories_snap._id AS snap_id,
    memories_media.format,
    memories_media.download_url,
    memories_snap.longitude,
    memories_snap.latitude,
    memories_snap.media_key,
    memories_snap.media_iv,
    memories_snap.snap_capture_time,
    memories_snap.duration,
    memories_snap.is_favorite,
    memories_snap.front_facing
FROM memories_snap
JOIN memories_media
    ON memories_snap.media_id = memories_media._id;"""

    if download_files:
        download_folder = os.path.join(output_path, "snaps")
        os.makedirs(download_folder, exist_ok=True)

    conn = sqlite3.connect(memories_path)
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()

    # Pre-filter rows with a download URL so progress count is accurate
    downloadable_rows = [r for r in rows if r[3]]
    total = len(downloadable_rows)
    download_index = 0
    skipped_out_of_range = 0
    skipped_unknown_date = 0
    snaps = []

    for row in rows:
        media_id = str(row[0])
        snap_id = str(row[1])
        media_format = row[2]
        media_url = row[3]
        longitude = row[4]
        latitude = row[5]
        media_key_b64 = row[6]
        media_iv_b64 = row[7]
        snap_capture_time_ms = row[8]
        duration = row[9]
        is_favorite = bool(row[10]) if row[10] is not None else False
        front_facing = bool(row[11]) if row[11] is not None else False

        if not media_url:
            continue

        key_hex = base64.b64decode(media_key_b64).hex() if media_key_b64 else ""
        iv_hex = base64.b64decode(media_iv_b64).hex() if media_iv_b64 else ""

        capture_time = None
        if snap_capture_time_ms is not None:
            try:
                dt = datetime.fromtimestamp(snap_capture_time_ms / 1000.0, tz=timezone.utc)
                capture_time = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except Exception:
                capture_time = str(snap_capture_time_ms)

        snap = {
            "snap_id": snap_id,
            "media_id": media_id,
            "capture_time": capture_time,
            "duration": duration,
            "is_favorite": is_favorite,
            "front_facing": front_facing,
            "media_format": media_format,
            "region": None,
            "latitude": latitude,
            "longitude": longitude,
            "key": key_hex,
            "iv": iv_hex,
            "media_url": media_url,
            "file_path": None,
        }

        date_ok = snap_in_date_range(capture_time, date_from, date_to)
        if download_files and not date_ok:
            if not capture_time:
                skipped_unknown_date += 1
            else:
                skipped_out_of_range += 1

        if download_files and date_ok:
            download_index += 1
            try:
                _log(f"Downloading snap {download_index}/{total}: {snap_id}")
                bin_path = os.path.join(download_folder, f"{snap_id}.bin")
                downloaded = wget.download(media_url, out=bin_path)

                key = base64.b64decode(media_key_b64)
                iv = base64.b64decode(media_iv_b64)

                if media_format == 'image_jpeg':
                    out_path = downloaded + "-decrypted.jpeg"
                elif media_format in ('video_hevc', 'video_avc'):
                    out_path = downloaded + "-decrypted.mp4"
                else:
                    out_path = downloaded + "-decrypted.bin"

                with open(downloaded, 'rb') as f:
                    encrypted = f.read()
                with open(out_path, 'wb') as f:
                    cipher = AES.new(key[:32], AES.MODE_CBC, iv)
                    f.write(cipher.decrypt(encrypted))
                os.remove(downloaded)

                snap["file_path"] = out_path
                _log(f"Snap {download_index}/{total} saved: {os.path.basename(out_path)}", "OK")

            except Exception as e:
                _log(f"Download/decrypt error for snap {snap_id}: {e}", "ERROR")

        snaps.append(snap)

    if download_files and (date_from or date_to):
        _log(
            f"Date filter ({date_from or '…'} to {date_to or '…'}): "
            f"{skipped_out_of_range} snap(s) skipped (outside range), "
            f"{skipped_unknown_date} snap(s) skipped (capture time unknown)",
            "INFO",
        )

    return snaps
