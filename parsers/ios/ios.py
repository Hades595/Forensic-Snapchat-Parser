import os
import shutil
import sqlite3
import csv
import wget
from string import Template
from datetime import datetime, timezone
from Crypto.Cipher import AES
from parsers.ios.reporting import generate_report

SQLITE_FILE_HEADER = "SQLite format 3\x00"
DEFAULT_PAGESIZE = 1024
KEY_SIZE = 32
SALT_SIZE = 16

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
FROM ZGALLERYSNAP WHERE ZMEDIAID = '$SNAPID'
"""


def process_ios(
    case_name: str,
    input_path: str,
    cipherkey: str,
    output_path: str,
    download_files: bool,
    examiner: str = "",
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
        log_callback=_log,
    )

    report_path = generate_report(case_name, snaps, case_folder, examiner)
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
            f.write(AES.new(key[:32], AES.MODE_CBC, tblist[-48:-32]).decrypt(tblist[:-48]))
            f.write(b'\x00' * 48)


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
    decrypted_wal = os.path.join(output_path, "gallery.decrypted.sqlite-wal")
    recovered_path = os.path.join(output_path, "gallery.recovered.sqlite")

    _log("Decrypting gallery database...")
    decrypt_file(cipherkey, gallery_path, decrypted_path)

    if gallery_wal_path and os.path.exists(gallery_wal_path):
        decrypt_file(cipherkey, gallery_wal_path, decrypted_wal)

    _log("Repairing gallery database...")
    repair_sqlite_db(decrypted_path, recovered_path)
    _log("Gallery database recovered.", "OK")

    return parse_gallery(recovered_path, output_path)


def _convert_key_to_str(key):
    if isinstance(key, bytes):
        return ''.join(format(byte, '02x') for byte in key)
    return key or ""


def parse_gallery(gallery_recovered_path, output_path) -> list:
    conn = sqlite3.connect(gallery_recovered_path)
    cur = conn.cursor()
    conn.execute("PRAGMA wal_checkpoint(FULL);")
    cur.execute(gallery_db_query)
    rows = cur.fetchall()
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


def parse_scdb(scdb_path, output_path, download_files, gallery_snaps, log_callback=None) -> list:
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

            if download_files and media_url:
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
    return gallery_snaps
