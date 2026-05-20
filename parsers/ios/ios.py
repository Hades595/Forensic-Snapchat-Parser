import os
import shutil
import sqlite3
import csv
import wget
from string import Template
from Crypto.Cipher import AES

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

def process_ios(case_name: str, input_path: str, cipherkey: str, output_path: str, download_files: bool) -> str:

    scdb_found = None
    gallery_found = None
    cipherkey = cipherkey
    
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

    gallery_wal = gallery_found + "-wal"
    if os.path.exists(gallery_wal):
        shutil.copy2(gallery_wal, os.path.join(case_folder, os.path.basename(gallery_wal)))
        print("Copied Gallery WAL:", gallery_wal)
        gallery_wal_path = os.path.join(case_folder, os.path.basename(gallery_wal))

    print("Files copied successfully.")
    
    decrypt_gallery(cipherkey=cipherkey, gallery_path=gallery_dest, gallery_wal_path=gallery_wal_path, output_path=case_folder)
    parse_scdb(scdb_path=scdb_path, output_path=case_folder, download_files=download_files)
    
    
    return "iOS Snapchat databases copied successfully"

def read_file(path, type='bytes'):
    '''
    Read file at path, specify read type <'bytes'> or <'text'>
    '''
    mode = {'bytes' : 'rb', 'text' : 'r'}
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
    salt = blist[:SALT_SIZE]
    with open(out_path, 'wb') as f:
        f.write(SQLITE_FILE_HEADER.encode())
        for i in range(0, len(blist), DEFAULT_PAGESIZE):
            tblist = blist[i:i + DEFAULT_PAGESIZE] if i > 0 else blist[SALT_SIZE:i + DEFAULT_PAGESIZE]
            f.write(AES.new(key[:32], AES.MODE_CBC, tblist[-48:-32]).decrypt(tblist[:-48]))
            f.write(b'\x00'*48)

def repair_sqlite_db(input_db, output_db):

    dump_file = os.path.join(os.path.dirname(output_db), "clean_dump.sql")

    # Step 1 — Remove indexes
    conn = sqlite3.connect(input_db)
    cursor = conn.cursor()

    cursor.execute("PRAGMA writable_schema=ON;")
    cursor.execute("DELETE FROM sqlite_master WHERE type='index';")
    cursor.execute("PRAGMA writable_schema=OFF;")

    conn.commit()
    conn.close()

    # Step 2 — Dump database
    conn = sqlite3.connect(input_db)

    with open(dump_file, "w", encoding="utf-8") as f:
        for line in conn.iterdump():
            f.write(f"{line}\n")

    conn.close()

    # Step 3 — Rebuild clean database
    conn = sqlite3.connect(output_db)

    with open(dump_file, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    conn.commit()
    conn.close()

    print("Database recovered:", output_db)

def decrypt_gallery(cipherkey, gallery_path, gallery_wal_path, output_path):
    cipherkey = convert_to_bytes(cipherkey)
    
    decrypt_file(cipherkey, gallery_path, os.path.join(output_path, "gallery.decrypted.sqlite"))
    decrypt_file(cipherkey, gallery_wal_path, os.path.join(output_path, "gallery.decrypted.sqlite-wal"))
    
    repair_sqlite_db(os.path.join(output_path, "gallery.decrypted.sqlite"), os.path.join(output_path, "gallery.recovered.sqlite"))
    repair_sqlite_db(os.path.join(output_path, "gallery.decrypted.sqlite-wal"), os.path.join(output_path, "gallery.recovered.sqlite-wal"))
    
    parse_gallery(os.path.join(output_path, "gallery.recovered.sqlite"), output_path=output_path)

def parse_gallery(gallery_recovered_path, output_path):
    conn = sqlite3.connect(gallery_recovered_path)
    cur = conn.cursor()
    conn.execute("PRAGMA wal_checkpoint(FULL);")
    cur.execute(gallery_db_query)

    output = cur.fetchall()

    def convert_to_str(key):
        return ''.join(format(byte, '02x') for byte in key)

    with open(os.path.join(output_path, "database.csv"), 'w', encoding="utf-8") as f: 
        f.write("SNAP_ID,Region,Latitude,Longitude,Key,IV\n")       
        for row in output:
            snap_id = row[0]
            region = "\"" + row[1] + "\"" if row[1] else ""
            lat = str(row[2]) if row[2] else ""
            lon = str(row[3]) if row[3] else ""
            key = convert_to_str(row[4]) if row[4] else ""
            iv = convert_to_str(row[5]) if row[5] else ""
            string_row = ",".join([snap_id, region, lat, lon, key, iv]) + "\n"
        
            try:
                f.write(string_row)
            except:

                print(string_row)
    conn.commit()
    conn.close()

def parse_scdb(scdb_path, output_path, download_files):
    
    csv_file = os.path.join(output_path, "database.csv")
    
    if download_files:
        download_folder = os.path.join(output_path, "snaps")
        os.makedirs(download_folder, exist_ok=True)
    
    conn = sqlite3.connect(scdb_path)
    cur = conn.cursor()

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            try:
                snap_id = row[0]
                query = Template(scdb_query).substitute(SNAPID=snap_id)
                cur.execute(query)
                output = cur.fetchall()
                if(len(output) == 0): #Empty so useless
                    continue
                
                if (download_files == True):
                    #Download the file
                    url = output[0][2]
                    file = wget.download(url, out=download_folder)
                    file_format = output[0][3]

                    #Decrypt the file
                    key = convert_to_bytes(row[4])
                    iv = convert_to_bytes(row[5])

                    #Add extention
                    if (file_format == 'image_jpeg'):
                        path = file + "-decrypted.jpeg"
                    elif (file_format == 'video_hevc' or file_format == 'video_avc' ):
                        path = file + "-decrypted.mp4"

                    with open(file, 'rb') as f:
                        temp = f.read()

                    with open(path, 'wb') as f:
                        f.write(AES.new(key[:32], AES.MODE_CBC, iv).decrypt(temp))
                    os.remove(file)
            except:
                print("Failed getting file: " + row)
