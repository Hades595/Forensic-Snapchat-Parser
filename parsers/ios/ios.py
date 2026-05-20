import os
import shutil
import sqlite3
import csv
import wget
from string import Template
from datetime import datetime, timezone, timedelta
from Crypto.Cipher import AES
from parsers.html.report import generate_report
from parsers.ios.arroyo import process_arroyo_ios

SQLITE_FILE_HEADER = "SQLite format 3\x00"
DEFAULT_PAGESIZE = 1024
KEY_SIZE = 32
SALT_SIZE = 16

# Apple Core Data timestamps start at 2001-01-01 UTC, not Unix epoch
CORE_DATA_EPOCH_OFFSET = 978307200

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


def _convert_core_data_ts(ts):
    if ts is None:
        return ''
    try:
        dt = datetime.fromtimestamp(float(ts) + CORE_DATA_EPOCH_OFFSET, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception:
        return str(ts)


def process_ios(case_name: str, input_path: str, cipherkey: str, output_path: str, download_files: bool) -> str:

    scdb_found = None
    gallery_found = None

    # -------------------------
    # Locate Snapchat databases
    # -------------------------

    for root, dirs, files in os.walk(input_path):
        for file in files:

            if file.startswith("scdb-") and file.endswith(".sqlite3"):
                scdb_found = os.path.join(root, file)

            if file == "gallery.encrypteddb":
                gallery_found = os.path.join(root, file)

        if scdb_found and gallery_found:
            break

    print("SCDB Path:", scdb_found)
    print("Gallery Path:", gallery_found)

    if not scdb_found:
        return "SCDB database not found"

    if not gallery_found:
        return "Gallery database not found"

    # -------------------------
    # Create Case Folder
    # -------------------------

    case_folder = os.path.join(output_path, case_name)
    os.makedirs(case_folder, exist_ok=True)

    print("Case folder:", case_folder)

    # -------------------------
    # Copy SCDB + WAL
    # -------------------------

    scdb_dest = os.path.join(case_folder, os.path.basename(scdb_found))
    shutil.copy2(scdb_found, scdb_dest)
    scdb_path = scdb_dest

    scdb_wal = scdb_found + "-wal"
    if os.path.exists(scdb_wal):
        shutil.copy2(scdb_wal, os.path.join(case_folder, os.path.basename(scdb_wal)))
        print("Copied SCDB WAL:", scdb_wal)

    # -------------------------
    # Copy Gallery DB + WAL
    # -------------------------

    gallery_dest = os.path.join(case_folder, os.path.basename(gallery_found))
    shutil.copy2(gallery_found, gallery_dest)

    gallery_wal_path = None
    gallery_wal = gallery_found + "-wal"
    if os.path.exists(gallery_wal):
        shutil.copy2(gallery_wal, os.path.join(case_folder, os.path.basename(gallery_wal)))
        print("Copied Gallery WAL:", gallery_wal)
        gallery_wal_path = os.path.join(case_folder, os.path.basename(gallery_wal))

    print("Files copied successfully.")

    snap_list = decrypt_gallery(
        cipherkey=cipherkey,
        gallery_path=gallery_dest,
        gallery_wal_path=gallery_wal_path,
        output_path=case_folder,
    )

    snap_list = parse_scdb(
        scdb_path=scdb_path,
        output_path=case_folder,
        download_files=download_files,
        snap_list=snap_list,
    )

    conversations, messages = process_arroyo_ios(
        input_path=input_path,
        output_path=case_folder,
    )

    report_path = generate_report(
        case_name=case_name,
        platform='IOS',
        output_path=case_folder,
        snaps=snap_list,
        conversations=conversations,
        messages=messages,
    )
    print("Report generated:", report_path)

    return "iOS Snapchat databases copied successfully"


def read_file(path, type='bytes'):
    mode = {'bytes': 'rb', 'text': 'r'}
    try:
        with open(path, mode[type]) as f:
            file = f.read()
    except Exception as e:
        print(f"Failed to open file : {path}")
        print(f"Error raised : {e}")
    return file


def convert_to_bytes(input):
    if type(input) == str:
        return bytes.fromhex(input.strip())
    elif type(input) == bytes:
        return input
    else:
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

    print("Database recovered:", output_db)


def decrypt_gallery(cipherkey, gallery_path, gallery_wal_path, output_path):
    cipherkey = convert_to_bytes(cipherkey)

    decrypt_file(cipherkey, gallery_path, os.path.join(output_path, "gallery.decrypted.sqlite"))

    if gallery_wal_path and os.path.exists(gallery_wal_path):
        decrypt_file(cipherkey, gallery_wal_path, os.path.join(output_path, "gallery.decrypted.sqlite-wal"))
        repair_sqlite_db(os.path.join(output_path, "gallery.decrypted.sqlite"), os.path.join(output_path, "gallery.recovered.sqlite"))
        repair_sqlite_db(os.path.join(output_path, "gallery.decrypted.sqlite-wal"), os.path.join(output_path, "gallery.recovered.sqlite-wal"))
    else:
        repair_sqlite_db(os.path.join(output_path, "gallery.decrypted.sqlite"), os.path.join(output_path, "gallery.recovered.sqlite"))

    return parse_gallery(os.path.join(output_path, "gallery.recovered.sqlite"), output_path=output_path)


def parse_gallery(gallery_recovered_path, output_path):
    conn = sqlite3.connect(gallery_recovered_path)
    cur = conn.cursor()
    conn.execute("PRAGMA wal_checkpoint(FULL);")
    cur.execute(gallery_db_query)
    rows = cur.fetchall()
    conn.commit()
    conn.close()

    def bytes_to_hex(b):
        return ''.join(format(byte, '02x') for byte in b)

    snap_list = []

    with open(os.path.join(output_path, "database.csv"), 'w', encoding="utf-8") as f:
        f.write("SNAP_ID,Region,Latitude,Longitude,Key,IV\n")
        for row in rows:
            snap_id = row[0]
            region = row[1] or ''
            lat = row[2]
            lon = row[3]
            key = bytes_to_hex(row[4]) if row[4] else ''
            iv = bytes_to_hex(row[5]) if row[5] else ''

            region_csv = '"' + region + '"' if region else ''
            lat_csv = str(lat) if lat is not None else ''
            lon_csv = str(lon) if lon is not None else ''
            csv_row = ",".join([snap_id, region_csv, lat_csv, lon_csv, key, iv]) + "\n"

            try:
                f.write(csv_row)
            except Exception:
                print("Failed to write row:", snap_id)

            snap_list.append({
                'snap_id': snap_id,
                'region': region,
                'latitude': lat,
                'longitude': lon,
                'key': key,
                'iv': iv,
                # populated by parse_scdb
                'capture_time': '',
                'duration': None,
                'download_url': '',
                'format': '',
                'file_path': '',
            })

    return snap_list


def parse_scdb(scdb_path, output_path, download_files, snap_list):

    if download_files:
        download_folder = os.path.join(output_path, "snaps")
        os.makedirs(download_folder, exist_ok=True)

    conn = sqlite3.connect(scdb_path)
    cur = conn.cursor()

    for snap in snap_list:
        try:
            snap_id = snap['snap_id']
            query = Template(scdb_query).substitute(SNAPID=snap_id)
            cur.execute(query)
            result = cur.fetchall()

            if not result:
                continue

            row = result[0]
            snap['capture_time'] = _convert_core_data_ts(row[0])
            snap['duration'] = row[1]
            snap['download_url'] = row[2] or ''
            snap['format'] = row[3] or ''

            if download_files and row[2]:
                url = row[2]
                file = wget.download(url, out=download_folder)
                file_format = snap['format']

                key = convert_to_bytes(snap['key'])
                iv = convert_to_bytes(snap['iv'])

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
            print("Failed processing snap:", snap.get('snap_id', ''), e)

    conn.close()
    return snap_list
