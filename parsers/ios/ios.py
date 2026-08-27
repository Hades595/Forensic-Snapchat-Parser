import os
import shutil
import sqlite3
import csv
import plistlib
import wget
from string import Template
from datetime import datetime, timezone
from Crypto.Cipher import AES
from parsers.ios.reporting import generate_report
from parsers.chats.arroyo import find_arroyo, parse_arroyo, load_conversation_titles, find_names_db_ios, load_names_ios
from parsers.ios.main_db import parse_friends_ios, parse_user_profile_ios
from parsers.date_filter import snap_in_date_range

SQLITE_FILE_HEADER = "SQLite format 3\x00"
DEFAULT_PAGESIZE = 1024
KEY_SIZE = 32
SALT_SIZE = 16
RESERVED_SIZE = 48   # bytes reserved at end of each encrypted page (IV + tail)

# SQLite WAL file structure constants
WAL_MAGIC = b'\x37\x7f\x06\x82'   # big-endian WAL magic (0x377f0682)
WAL_MAGIC_ALT = b'\x37\x7f\x06\x83'  # checksum variant
WAL_HEADER_SIZE = 32               # bytes — WAL file header (unencrypted)
WAL_FRAME_HEADER_SIZE = 24         # bytes — per-frame header (unencrypted)

gallery_db_query = """
SELECT
	snap_key_iv.snap_id AS 'SNAP ID',
	snap_address_title.address_title AS 'Region',
	snap_location_table.latitude AS 'Latitude',
	snap_location_table.longitude AS 'Longitude',
	snap_key_iv.key AS 'Key',
	snap_key_iv.iv AS 'IV'
FROM
	snap_key_iv
LEFT JOIN
	snap_location_table ON snap_key_iv.snap_id = snap_location_table.snap_id
LEFT JOIN
	snap_address_title ON snap_address_title.snap_id = snap_key_iv.snap_id
"""

scdb_query = """
SELECT
ZGALLERYSNAP.ZCAPTURETIMEUTC,
ZGALLERYSNAP.ZDURATION,
ZGALLERYSNAP.ZMEDIADOWNLOADURL,
ZGALLERYSNAP.ZSERVLETMEDIAFORMAT
FROM ZGALLERYSNAP WHERE UPPER(ZMEDIAID) = UPPER('$SNAPID')
"""

scdb_primary_query = """
SELECT
    ZSNAPID,
    ZCAPTURETIMEUTC,
    ZDURATION,
    ZINFINITEDURATION,
    ZMEDIADOWNLOADURL,
    ZSERVLETMEDIAFORMAT,
    ZCAMERAFRONTFACING,
    ZENCRYPTION
FROM ZGALLERYSNAP
ORDER BY ZCAPTURETIMEUTC ASC
"""


def process_ios(
    case_name: str,
    input_path: str,
    cipherkey: str,
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

    scdb_found = None
    gallery_found = None

    for root, dirs, files in os.walk(input_path):
        for file in files:
            if file.startswith("scdb-") and file.endswith(".sqlite3"):
                scdb_found = os.path.join(root, file)
            if file == "gallery.encrypteddb":
                gallery_found = os.path.join(root, file)
        if scdb_found and gallery_found:
            break

    _log(f"SCDB Path: {scdb_found}")
    _log(f"Gallery Path: {gallery_found}")

    if not scdb_found:
        return "SCDB database not found"
    if not gallery_found:
        return "Gallery database not found"

    case_folder = os.path.join(output_path, case_name)
    os.makedirs(case_folder, exist_ok=True)
    _log(f"Case folder: {case_folder}")

    scdb_dest = os.path.join(case_folder, os.path.basename(scdb_found))
    shutil.copy2(scdb_found, scdb_dest)
    scdb_path = scdb_dest

    scdb_wal = scdb_found + "-wal"
    if os.path.exists(scdb_wal):
        shutil.copy2(scdb_wal, os.path.join(case_folder, os.path.basename(scdb_wal)))
        _log(f"Copied SCDB WAL: {scdb_wal}")

    gallery_dest = os.path.join(case_folder, os.path.basename(gallery_found))
    shutil.copy2(gallery_found, gallery_dest)

    gallery_wal_path = None
    gallery_wal = gallery_found + "-wal"
    if os.path.exists(gallery_wal):
        gallery_wal_dest = os.path.join(case_folder, os.path.basename(gallery_wal))
        shutil.copy2(gallery_wal, gallery_wal_dest)
        _log(f"Copied Gallery WAL: {gallery_wal}")
        gallery_wal_path = gallery_wal_dest

    _log("Files copied successfully.")

    gallery_snaps = decrypt_gallery(
        cipherkey=cipherkey,
        gallery_path=gallery_dest,
        gallery_wal_path=gallery_wal_path,
        output_path=case_folder,
        log_callback=_log,
    )

    snaps = parse_scdb(
        scdb_path=scdb_path,
        output_path=case_folder,
        download_files=download_files,
        gallery_snaps=gallery_snaps,
        date_from=date_from,
        date_to=date_to,
        log_callback=_log,
    )

    # Merge SCDB primary snaps (ZGALLERYSNAP) — adds snaps that carry their own
    # AES key in the ZENCRYPTION blob and are not already in the gallery DB.
    scdb_primary = parse_scdb_primary(scdb_path, log_callback=_log)
    existing_ids = {s["snap_id"] for s in snaps}
    for s in scdb_primary:
        if s["snap_id"] not in existing_ids:
            snaps.append(s)
    _log(f"Total snaps after SCDB merge: {len(snaps)}", "OK")

    # Extract account profile from ZGALLERYPROFILE in already-copied scdb
    user_profile = parse_user_profile_ios(scdb_path)
    _log(f"User profile: user_id={user_profile.get('user_id') or '(unknown)'}")

    # Build snap_id → snap dict for cross-referencing with arroyo Snap messages
    snap_lookup = {s["snap_id"]: s for s in snaps if s.get("snap_id")}

    arroyo_src = find_arroyo(input_path)
    chats = []
    chat_sources = []
    conv_titles = {}
    friends = []
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
        names_src = find_names_db_ios(input_path)
        names = {}
        if names_src:
            names_dest = os.path.join(case_folder, "friending_notification_snapchatter.db")
            shutil.copy2(names_src, names_dest)
            _log(f"friending_notification_snapchatter.db copied: {names_dest}")
            names = load_names_ios(names_dest)
            friends = parse_friends_ios(names_dest)
            _log(f"friending_notification_snapchatter.db: {len(friends)} friends")
            chat_sources.append("friending_notification_snapchatter.db")
        chats = parse_arroyo(arroyo_dest, snap_lookup=snap_lookup, names=names, log_callback=_log)

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

    snap_sources = [
        "gallery.encrypteddb", "gallery.recovered.sqlite",
        os.path.basename(scdb_path), "ZGALLERYSNAP (SCDB primary)",
    ]
    report_path = generate_report(
        case_name, snaps, chats, snap_sources, chat_sources, case_folder, examiner,
        friends=friends, user_profile=user_profile, conv_titles=conv_titles,
    )
    _log(f"Report generated: {report_path}", "OK")
    return report_path


def read_file(path, type='bytes'):
    mode = {'bytes': 'rb', 'text': 'r'}
    try:
        with open(path, mode[type]) as f:
            return f.read()
    except Exception as e:
        print(f"Failed to open file: {path} — {e}")


def convert_to_bytes(input):
    if isinstance(input, str):
        return bytes.fromhex(input.strip())
    elif isinstance(input, bytes):
        return input
    raise Exception('Input type unrecognised')


def decrypt_file(key, db_path, out_path):
    blist = read_file(db_path)
    with open(out_path, 'wb') as f:
        f.write(SQLITE_FILE_HEADER.encode())
        for i in range(0, len(blist), DEFAULT_PAGESIZE):
            tblist = blist[i:i + DEFAULT_PAGESIZE] if i > 0 else blist[SALT_SIZE:i + DEFAULT_PAGESIZE]
            data = tblist[:-48]
            if not data:
                continue
            # AES-CBC requires the plaintext length to be a multiple of 16.
            # Partial pages (file not a multiple of DEFAULT_PAGESIZE) are
            # truncated to the nearest 16-byte boundary to avoid a padding
            # error; any truncated tail bytes are negligible SQLite padding.
            remainder = len(data) % 16
            if remainder:
                data = data[:-remainder]
            if not data:
                continue
            f.write(AES.new(key[:32], AES.MODE_CBC, tblist[-48:-32]).decrypt(data))
            f.write(b'\x00' * 48)


def _validate_page1(page_bytes):
    """Return True if page_bytes looks like a valid decrypted SQLite page 1.

    Checks: correct SQLite magic (first 16 bytes), page size 1024 (bytes 16-17),
    and reserved-bytes field == 48 (byte 20).  These are fixed for Snapchat's
    gallery database format.
    """
    if len(page_bytes) < 24:
        return False
    if page_bytes[:16] != SQLITE_FILE_HEADER.encode():
        return False
    page_size = (page_bytes[16] << 8) | page_bytes[17]
    if page_size != DEFAULT_PAGESIZE:
        return False
    if page_bytes[20] != RESERVED_SIZE:
        return False
    return True


def _decrypt_page1(key, raw_page):
    """Try to decrypt WAL page 1 and return valid page bytes, or None.

    Attempts two modes and picks whichever produces a structurally valid
    SQLite page 1 (correct magic + page size 1024 + reserved bytes 48):

    Mode A — salt-skip: bytes 0-15 are the salt (same as the main DB file),
      so only bytes 16-975 (960 bytes) are AES-CBC encrypted.

    Mode B — full-page: all 976 bytes (0-975) are encrypted (no salt).
      Used when the WAL page carries the real SQLite magic in byte 0.
    """
    iv = raw_page[DEFAULT_PAGESIZE - RESERVED_SIZE:DEFAULT_PAGESIZE - RESERVED_SIZE + 16]

    # Mode A: salt-skip (first 16 bytes are the salt, not encrypted)
    data_a = raw_page[SALT_SIZE:DEFAULT_PAGESIZE - RESERVED_SIZE]
    remainder = len(data_a) % 16
    if remainder:
        data_a = data_a[:-remainder]
    if data_a:
        dec_a = AES.new(key[:32], AES.MODE_CBC, iv).decrypt(data_a)
        page_a = SQLITE_FILE_HEADER.encode() + dec_a + b'\x00' * RESERVED_SIZE
        if _validate_page1(page_a):
            return page_a

    # Mode B: full-page encryption (all 976 bytes encrypted)
    data_b = raw_page[:DEFAULT_PAGESIZE - RESERVED_SIZE]
    remainder = len(data_b) % 16
    if remainder:
        data_b = data_b[:-remainder]
    if data_b:
        dec_b = AES.new(key[:32], AES.MODE_CBC, iv).decrypt(data_b)
        page_b = dec_b + b'\x00' * RESERVED_SIZE
        if _validate_page1(page_b):
            return page_b

    return None   # decryption did not produce a valid header; caller should skip


def _decrypt_wal_pages(key, raw_wal):
    """Yield (page_number, page_bytes) for every frame in a WAL byte string.

    Page 1 is handled by _decrypt_page1() which tries both salt-skip and
    full-page encryption modes, validating the result.  If neither mode
    produces a valid SQLite header the frame is silently dropped so that
    the main database's page 1 (already applied by decrypt_file) is
    preserved.  All other pages use the standard full-page AES-CBC scheme.
    """
    if len(raw_wal) < WAL_HEADER_SIZE:
        return

    offset = WAL_HEADER_SIZE
    frame_size = WAL_FRAME_HEADER_SIZE + DEFAULT_PAGESIZE
    while offset + frame_size <= len(raw_wal):
        frame_header = raw_wal[offset:offset + WAL_FRAME_HEADER_SIZE]
        page_number = int.from_bytes(frame_header[:4], 'big')
        raw_page = raw_wal[offset + WAL_FRAME_HEADER_SIZE:offset + frame_size]
        offset += frame_size

        if page_number < 1:
            continue

        if page_number == 1:
            page_bytes = _decrypt_page1(key, raw_page)
            if page_bytes is not None:
                yield page_number, page_bytes
            # else: silently skip — main DB page 1 already in place
        else:
            # All other pages: full 976 bytes (0-975) are AES-CBC encrypted
            iv = raw_page[DEFAULT_PAGESIZE - RESERVED_SIZE:DEFAULT_PAGESIZE - RESERVED_SIZE + 16]
            data = raw_page[:DEFAULT_PAGESIZE - RESERVED_SIZE]
            remainder = len(data) % 16
            if remainder:
                data = data[:-remainder]
            if not data:
                continue
            decrypted = AES.new(key[:32], AES.MODE_CBC, iv).decrypt(data)
            yield page_number, decrypted + b'\x00' * RESERVED_SIZE


def apply_wal_to_db(key, wal_path, db_path, log_callback=None):
    """Apply WAL frames directly into the decrypted main database.

    Bypasses SQLite's checksum validation (which would fail because the
    WAL checksums were computed against encrypted page content, not the
    decrypted bytes we have in db_path).  Each WAL frame's page is written
    to its correct offset inside db_path so the data is available before
    repair_sqlite_db opens the file — without leaving a .sqlite-wal file
    that would trigger SQLite's own (failing) WAL-recovery path.
    """
    def _log(msg, lvl="INFO"):
        if log_callback:
            log_callback(msg, lvl)
        else:
            print(msg)

    raw_wal = read_file(wal_path)
    if not raw_wal:
        return 0

    applied = 0
    try:
        with open(db_path, 'r+b') as db_f:
            for page_number, page_bytes in _decrypt_wal_pages(key, raw_wal):
                db_offset = (page_number - 1) * DEFAULT_PAGESIZE
                db_f.seek(db_offset)
                db_f.write(page_bytes)
                applied += 1
    except Exception as e:
        _log(f"WAL application warning: {e}", "INFO")

    return applied


def repair_sqlite_db(input_db, output_db):
    dump_file = os.path.join(os.path.dirname(output_db), "clean_dump.sql")

    conn = sqlite3.connect(input_db)
    cursor = conn.cursor()
    cursor.execute("PRAGMA writable_schema=ON;")
    cursor.execute("DELETE FROM sqlite_master WHERE type='index';")
    cursor.execute("PRAGMA writable_schema=OFF;")
    conn.commit()
    conn.close()

    conn = sqlite3.connect(input_db)
    with open(dump_file, "w", encoding="utf-8") as f:
        for line in conn.iterdump():
            f.write(f"{line}\n")
    conn.close()

    if os.path.exists(output_db):
        os.remove(output_db)

    conn = sqlite3.connect(output_db)
    with open(dump_file, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def decrypt_gallery(cipherkey, gallery_path, gallery_wal_path, output_path, log_callback=None) -> list:
    def _log(msg, lvl="INFO"):
        if log_callback:
            log_callback(msg, lvl)
        else:
            print(msg)

    cipherkey = convert_to_bytes(cipherkey)

    decrypted_path = os.path.join(output_path, "gallery.decrypted.sqlite")
    recovered_path = os.path.join(output_path, "gallery.recovered.sqlite")

    _log("Decrypting gallery database...")
    decrypt_file(cipherkey, gallery_path, decrypted_path)

    if gallery_wal_path and os.path.exists(gallery_wal_path):
        _log("Applying gallery WAL...")
        applied = apply_wal_to_db(cipherkey, gallery_wal_path, decrypted_path, log_callback=_log)
        _log(f"WAL: {applied} page(s) merged into gallery database.", "OK")

    _log("Repairing gallery database...")
    repair_sqlite_db(decrypted_path, recovered_path)
    _log("Gallery database recovered.", "OK")

    return parse_gallery(recovered_path, output_path, log_callback=_log)


def _convert_key_to_str(key):
    if isinstance(key, bytes):
        return ''.join(format(byte, '02x') for byte in key)
    return key or ""


def parse_gallery(gallery_recovered_path, output_path, log_callback=None) -> list:
    def _log(msg, lvl="INFO"):
        if log_callback:
            log_callback(msg, lvl)
        else:
            print(msg)

    conn = sqlite3.connect(gallery_recovered_path)
    cur = conn.cursor()
    conn.execute("PRAGMA wal_checkpoint(FULL);")
    try:
        cur.execute(gallery_db_query)
        rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        _log(f"Gallery query failed ({e}) — no snap keys recovered", "INFO")
        conn.close()
        return []
    conn.commit()
    conn.close()

    snaps = []
    csv_rows = []

    for row in rows:
        snap_id = row[0]
        region = row[1] or ""
        lat = row[2]
        lon = row[3]
        key = _convert_key_to_str(row[4])
        iv = _convert_key_to_str(row[5])

        snaps.append({
            "snap_id": snap_id,
            "media_id": None,
            "capture_time": None,
            "duration": None,
            "media_format": None,
            "region": region or None,
            "latitude": lat,
            "longitude": lon,
            "key": key,
            "iv": iv,
            "media_url": None,
            "file_path": None,
        })

        csv_rows.append((
            snap_id,
            f'"{region}"' if region else "",
            str(lat) if lat is not None else "",
            str(lon) if lon is not None else "",
            key,
            iv,
        ))

    csv_path = os.path.join(output_path, "database.csv")
    with open(csv_path, 'w', encoding="utf-8") as f:
        f.write("SNAP_ID,Region,Latitude,Longitude,Key,IV\n")
        for row in csv_rows:
            try:
                f.write(",".join(row) + "\n")
            except Exception as e:
                print("CSV write error:", e)

    return snaps


def _parse_snap_encryption(blob):
    """Extract (key_hex, iv_hex) from a ZENCRYPTION NSKeyedArchiver binary plist.

    The blob is an NSKeyedArchiver-encoded SCMemoriesSnapEncryption object that
    carries the AES-256 key (32 bytes, field 'KEY') and optionally an IV (16 bytes).
    Returns (None, None) on any parsing error.
    """
    if not blob:
        return None, None
    try:
        plist   = plistlib.loads(blob)
        objects = plist.get('$objects', [])
        root_uid = plist.get('$top', {}).get('root')
        if root_uid is None:
            return None, None
        root = objects[root_uid]
        if not isinstance(root, dict):
            return None, None

        key_bytes = iv_bytes = None

        # Locate the 32-byte AES key
        for fname in ('KEY', 'SKEY', 'key'):
            ref = root.get(fname)
            if ref is not None:
                val = objects[ref]
                if isinstance(val, bytes) and len(val) == KEY_SIZE:
                    key_bytes = val
                    break

        # Locate the 16-byte IV (may be absent; derive from key if missing)
        for fname in ('IV', 'SIV', 'iv'):
            ref = root.get(fname)
            if ref is not None:
                val = objects[ref]
                if isinstance(val, bytes) and len(val) == 16:
                    iv_bytes = val
                    break

        # Fallback: find any 16-byte blob in $objects (first one that isn't the key)
        if iv_bytes is None:
            for obj in objects:
                if isinstance(obj, bytes) and len(obj) == 16:
                    iv_bytes = obj
                    break

        return (
            key_bytes.hex() if key_bytes else None,
            iv_bytes.hex()  if iv_bytes  else None,
        )
    except Exception:
        return None, None


def parse_scdb_primary(scdb_path, log_callback=None) -> list:
    """Parse ZGALLERYSNAP from scdb-*.sqlite3 as a primary snap source.

    Returns snap dicts in the same format as parse_gallery(), including the
    AES key and IV extracted from each row's ZENCRYPTION NSKeyedArchiver blob.
    Capture time is converted from Apple epoch (seconds since 2001-01-01 UTC).
    """
    def _log(msg, lvl="INFO"):
        if log_callback:
            log_callback(msg, lvl)
        else:
            print(msg)

    snaps = []
    try:
        conn = sqlite3.connect(scdb_path)
        conn.execute("PRAGMA wal_checkpoint(FULL);")
        cur = conn.cursor()
        cur.execute(scdb_primary_query)
        rows = cur.fetchall()
        conn.close()
    except sqlite3.OperationalError as e:
        _log(f"SCDB primary query failed ({e})", "INFO")
        return snaps

    for (snap_id_raw, capture_ts, duration, infinite_dur,
         media_url, media_format, front_facing, enc_blob) in rows:
        if not snap_id_raw:
            continue

        snap_id = snap_id_raw.lower()

        capture_time = None
        if capture_ts is not None:
            try:
                dt = datetime.fromtimestamp(capture_ts + 978307200, tz=timezone.utc)
                capture_time = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except Exception:
                capture_time = str(capture_ts)

        key_hex, iv_hex = _parse_snap_encryption(enc_blob)

        snaps.append({
            "snap_id":      snap_id,
            "media_id":     None,
            "capture_time": capture_time,
            "duration":     None if infinite_dur else duration,
            "media_format": media_format,
            "region":       None,
            "latitude":     None,
            "longitude":    None,
            "key":          key_hex or "",
            "iv":           iv_hex  or "",
            "media_url":    media_url,
            "file_path":    None,
            "front_facing": bool(front_facing),
            "is_favorite":  None,
        })

    _log(f"SCDB primary: {len(snaps)} snap(s) from ZGALLERYSNAP")
    return snaps


def parse_scdb(scdb_path, output_path, download_files, gallery_snaps, date_from=None, date_to=None, log_callback=None) -> list:
    def _log(msg, lvl="INFO"):
        if log_callback:
            log_callback(msg, lvl)
        else:
            print(msg)

    if download_files:
        download_folder = os.path.join(output_path, "snaps")
        os.makedirs(download_folder, exist_ok=True)

    conn = sqlite3.connect(scdb_path)
    cur = conn.cursor()

    downloadable = [s for s in gallery_snaps]
    total = len(downloadable)
    skipped_out_of_range = 0
    skipped_unknown_date = 0

    for i, snap in enumerate(downloadable):
        try:
            query = Template(scdb_query).substitute(SNAPID=snap["snap_id"])
            cur.execute(query)
            result = cur.fetchone()
            if not result:
                continue

            capture_ts, duration, media_url, media_format = result

            if capture_ts is not None:
                try:
                    dt = datetime.fromtimestamp(capture_ts + 978307200, tz=timezone.utc)
                    snap["capture_time"] = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                except Exception:
                    snap["capture_time"] = str(capture_ts)

            snap["duration"] = duration
            snap["media_url"] = media_url
            snap["media_format"] = media_format

            date_ok = snap_in_date_range(snap["capture_time"], date_from, date_to)
            if download_files and media_url and not date_ok:
                if (snap["capture_time"] or "") == "":
                    skipped_unknown_date += 1
                else:
                    skipped_out_of_range += 1

            if download_files and media_url and date_ok:
                _log(f"Downloading snap {i + 1}/{total}: {snap['snap_id']}")
                bin_path = os.path.join(download_folder, f"{snap['snap_id']}.bin")
                downloaded = wget.download(media_url, out=bin_path)

                key = convert_to_bytes(snap["key"])
                iv = convert_to_bytes(snap["iv"])

                if media_format == 'image_jpeg':
                    out_path = downloaded + "-decrypted.jpeg"
                elif media_format in ('video_hevc', 'video_avc'):
                    out_path = downloaded + "-decrypted.mp4"
                else:
                    out_path = downloaded + "-decrypted.bin"

                with open(downloaded, 'rb') as f:
                    encrypted = f.read()
                with open(out_path, 'wb') as f:
                    f.write(AES.new(key[:32], AES.MODE_CBC, iv).decrypt(encrypted))
                os.remove(downloaded)

                snap["file_path"] = out_path
                _log(f"Snap {i + 1}/{total} saved: {os.path.basename(out_path)}", "OK")

        except Exception as e:
            _log(f"Error processing snap {snap.get('snap_id')}: {e}", "ERROR")

    conn.close()

    if download_files and (date_from or date_to):
        _log(
            f"Date filter ({date_from or '…'} to {date_to or '…'}): "
            f"{skipped_out_of_range} snap(s) skipped (outside range), "
            f"{skipped_unknown_date} snap(s) skipped (capture time unknown)",
            "INFO",
        )

    return gallery_snaps
