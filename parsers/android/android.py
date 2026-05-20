import os
import shutil
import sqlite3 
import wget
import base64
from Crypto.Cipher import AES

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
    # Copy SCDB + WAL
    # -------------------------

    memories_dest = os.path.join(case_folder, os.path.basename(memories_found))
    shutil.copy2(memories_found, memories_dest)
    memories_path = memories_dest

    memories_wal = memories_found + "-wal"
    if os.path.exists(memories_wal):
        shutil.copy2(memories_wal, os.path.join(case_folder, os.path.basename(memories_wal)))
        print("Copied memories WAL:", memories_wal)
        
        
    parse_main(memories_path=memories_path, output_path=case_folder, download_files=download_files)
         
    
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
    output = cur.fetchall()
    
    if(len(output) == 0): #Empty so useless
        return
    
    for snap in output:
        snapid = snap[1]
        snapiv = snap[7]
        snapkey = snap[6]
        snapURL = snap[3]
        file_format = snap[2]
        
        if not snapURL:
            continue
                   
        if (download_files == True):
            #Download the file
            url = snapURL
            filename = os.path.join(download_folder, f"{snapid}.bin")
            
            file = wget.download(url, out=filename)

            #Decrypt the file
            key = base64.b64decode(snapkey)
            iv = base64.b64decode(snapiv)

            #Add extention
            if (file_format == 'image_jpeg'):
                path = file + "-decrypted.jpeg"
            elif (file_format == 'video_hevc' or file_format == 'video_avc' ):
                path = file + "-decrypted.mp4"
            
            #Encrypted File
            with open(file, 'rb') as f:
                temp = f.read()
                
            # Decrypt File
            with open(path, 'wb') as f:
                cipher = AES.new(key[:32], AES.MODE_CBC, iv)
                plaintext = cipher.decrypt(temp)
                f.write(plaintext)
            
            os.remove(file)
