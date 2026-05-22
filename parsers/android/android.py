import os
import shutil
import sqlite3
import base64
import wget
from Crypto.Cipher import AES
from parsers.android.reporting import generate_report


def process_android(
    case_name: str,
    input_path: str,
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
        log_callback=_log,
    )

    report_path = generate_report(case_name, snaps, case_folder, examiner)
    _log(f"Report generated: {report_path}", "OK")
    return report_path


def parse_main(memories_path, output_path, download_files, log_callback=None) -> list:

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
    memories_snap.media_iv
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

        if not media_url:
            continue

        key_hex = base64.b64decode(media_key_b64).hex() if media_key_b64 else ""
        iv_hex = base64.b64decode(media_iv_b64).hex() if media_iv_b64 else ""

        snap = {
            "snap_id": snap_id,
            "media_id": media_id,
            "capture_time": None,
            "duration": None,
            "media_format": media_format,
            "region": None,
            "latitude": latitude,
            "longitude": longitude,
            "key": key_hex,
            "iv": iv_hex,
            "media_url": media_url,
            "file_path": None,
        }

        if download_files:
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

    return snaps
