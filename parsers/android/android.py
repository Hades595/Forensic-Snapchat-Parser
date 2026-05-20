import os
import shutil
import sqlite3
import wget
import base64
from Crypto.Cipher import AES
from parsers.html.report import generate_report
from parsers.android.arroyo import process_arroyo_android


def process_android(case_name: str, input_path: str, output_path: str, download_files: bool) -> str:

    memories_found = None

    # -------------------------
    # Locate Snapchat databases
    # -------------------------

    for root, dirs, files in os.walk(input_path):
        for file in files:
            if file.startswith("memories") and file.endswith(".db"):
                memories_found = os.path.join(root, file)

        if memories_found:
            break

    print("memories Path:", memories_found)

    if not memories_found:
        return "memories.db database not found"

    # -------------------------
    # Create Case Folder
    # -------------------------

    case_folder = os.path.join(output_path, case_name)
    os.makedirs(case_folder, exist_ok=True)

    print("Case folder:", case_folder)

    # -------------------------
    # Copy memories DB + WAL
    # -------------------------

    memories_dest = os.path.join(case_folder, os.path.basename(memories_found))
    shutil.copy2(memories_found, memories_dest)
    memories_path = memories_dest

    memories_wal = memories_found + "-wal"
    if os.path.exists(memories_wal):
        shutil.copy2(memories_wal, os.path.join(case_folder, os.path.basename(memories_wal)))
        print("Copied memories WAL:", memories_wal)

    snap_list = parse_main(
        memories_path=memories_path,
        output_path=case_folder,
        download_files=download_files,
    )

    conversations, messages, friends = process_arroyo_android(
        input_path=input_path,
        output_path=case_folder,
    )

    report_path = generate_report(
        case_name=case_name,
        platform='ANDROID',
        output_path=case_folder,
        snaps=snap_list,
        conversations=conversations,
        messages=messages,
        friends=friends,
    )
    print("Report generated:", report_path)


def parse_main(memories_path, output_path, download_files):

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

    if not rows:
        return []

    snap_list = []

    with open(os.path.join(output_path, "database.csv"), 'w', encoding='utf-8') as csv_file:
        csv_file.write("snap_id,media_id,format,latitude,longitude,download_url\n")

        for row in rows:
            media_id = str(row[0]) if row[0] is not None else ''
            snap_id = str(row[1]) if row[1] is not None else ''
            file_format = row[2] or ''
            snap_url = row[3] or ''
            lon = row[4]
            lat = row[5]
            media_key = row[6] or ''
            media_iv = row[7] or ''

            lat_str = str(lat) if lat is not None else ''
            lon_str = str(lon) if lon is not None else ''
            csv_file.write(",".join([snap_id, media_id, file_format, lat_str, lon_str, snap_url]) + "\n")

            snap = {
                'snap_id': snap_id,
                'media_id': media_id,
                'format': file_format,
                'download_url': snap_url,
                'latitude': lat,
                'longitude': lon,
                'capture_time': '',
                'duration': None,
                'region': '',
                'file_path': '',
            }

            if not snap_url:
                snap_list.append(snap)
                continue

            if download_files:
                try:
                    filename = os.path.join(download_folder, f"{snap_id}.bin")
                    file = wget.download(snap_url, out=filename)

                    key = base64.b64decode(media_key)
                    iv = base64.b64decode(media_iv)

                    if file_format == 'image_jpeg':
                        decrypted_path = file + "-decrypted.jpeg"
                    elif file_format in ('video_hevc', 'video_avc'):
                        decrypted_path = file + "-decrypted.mp4"
                    else:
                        decrypted_path = file + "-decrypted.bin"

                    with open(file, 'rb') as f:
                        encrypted = f.read()

                    with open(decrypted_path, 'wb') as f:
                        f.write(AES.new(key[:32], AES.MODE_CBC, iv).decrypt(encrypted))

                    os.remove(file)
                    snap['file_path'] = os.path.join("snaps", os.path.basename(decrypted_path))

                except Exception as e:
                    print("Failed getting file:", snap_id, e)

            snap_list.append(snap)

    return snap_list
