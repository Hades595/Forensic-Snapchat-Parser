# PROJECT_STRUCTURE.md

> Architectural map for AI agents and developers. Enables quick navigation and dependency analysis.

## Overview

**Forensic Snapchat Parser** is a **desktop GUI application** built with **Python + PySide6**.

It parses Snapchat application data extracted from iOS and Android devices (via UFED), decrypts encrypted databases and media files, and exports forensic artifacts.

### Stack

| Layer       | Technology                                      |
| ----------- | ----------------------------------------------- |
| GUI         | PySide6 (Qt for Python), qt-material stylesheet |
| Crypto      | PyCryptodome — AES-CBC database + media decrypt |
| Database    | sqlite3 (stdlib) — read/repair SQLite databases |
| Keychain    | plistlib (stdlib) — iOS keychain plist parsing  |
| Downloads   | wget — optional CDN snap file downloads         |

---

## Project Tree

```
Forensic-Snapchat-Parser/
├── main.py                    # GUI entry point (SnapchatParserGUI)
├── logo.png                   # App logo displayed in header
├── requirements.txt           # pip dependencies
├── parsers/
│   ├── __init__.py
│   ├── android/
│   │   └── android.py         # Android parser — memories.db
│   ├── ios/
│   │   ├── ios.py             # iOS parser — gallery.encrypteddb + SCDB
│   │   └── keychain.py        # iOS keychain AES key extractor
│   ├── html/
│   │   └── report_template.html  # HTML report template (Jinja2-style)
│   └── sql/
│       ├── gallery_ios.sql    # Reference query for gallery.encrypteddb
│       ├── scdb_ios.sql       # Reference query for SCDB (ZGALLERYSNAP)
│       └── memories_android.sql  # Reference query for memories.db
└── Testing Data/              # UFED extraction samples (not committed to git)
```

**Statistics:**

- Directories: 6 source directories
- Source files: 6 Python, 3 SQL, 1 HTML
- Tests: none

---

## Run Commands

| Command                        | Description                              |
| ------------------------------ | ---------------------------------------- |
| `python main.py`               | Launch the GUI                           |
| `pip install -r requirements.txt` | Install base dependencies             |
| `pip install pycryptodome wget` | Install dependencies missing from requirements.txt |

---

## Source Structure

### Entry Point

- `main.py` — `SnapchatParserGUI(QWidget)` — main window, folder selection, platform detection, processing dispatch

### Platform Detection (`main.py:detect_platform`)

| Folder name pattern               | Platform |
| --------------------------------- | -------- |
| `com.snapchat.android`            | Android  |
| UUID (36-char hex, e.g. `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`) | iOS |

### iOS Parser (`parsers/ios/`)

| File          | Function             | Purpose                                                       |
| ------------- | -------------------- | ------------------------------------------------------------- |
| `keychain.py` | `process_keychain`   | Open keychain plist, find `egocipher.key.avoidkeyderivation`, return hex key |
| `ios.py`      | `process_ios`        | Orchestrator — copy DBs, decrypt gallery, parse SCDB          |
| `ios.py`      | `decrypt_gallery`    | AES-CBC page-by-page decrypt of `gallery.encrypteddb`         |
| `ios.py`      | `repair_sqlite_db`   | Drop indexes → dump SQL → rebuild clean SQLite                |
| `ios.py`      | `parse_gallery`      | Query `snap_key_iv` table, export `database.csv`              |
| `ios.py`      | `parse_scdb`         | Join CSV with SCDB, optionally download + decrypt snaps       |

### Android Parser (`parsers/android/`)

| File          | Function         | Purpose                                                        |
| ------------- | ---------------- | -------------------------------------------------------------- |
| `android.py`  | `process_android`| Orchestrator — find `memories.db`, copy it, dispatch parsing  |
| `android.py`  | `parse_main`     | Query `memories_snap + memories_media`, download + decrypt snaps |

### SQL Queries (`parsers/sql/`)

| File                    | Database              | Returns                                        |
| ----------------------- | --------------------- | ---------------------------------------------- |
| `gallery_ios.sql`       | `gallery.decrypted`   | snap_id, region, lat, lon, AES key, IV         |
| `scdb_ios.sql`          | `scdb-*.sqlite3`      | capture UTC, duration, CDN URL, media format   |
| `memories_android.sql`  | `memories*.db`        | snap_id, media_id, format, CDN URL, lat, lon, key, IV |

---

## Key Architectural Patterns

### iOS Gallery Decryption

`gallery.encrypteddb` uses SQLite Encrypted Extensions (SEE) — non-standard page encryption.

Decryption is manual, page-by-page (1024-byte pages), AES-CBC:
```
salt = file[:16]
per-page IV = page_bytes[-48:-32]   (penultimate 16 bytes of each page)
plaintext   = AES_CBC_decrypt(key[:32], IV, page_bytes[:-48])
output page = plaintext + 48 null bytes
```
The SQLite file header (`SQLite format 3\x00`) is written manually for page 0.
After decryption, `repair_sqlite_db` is called to strip corrupt indexes and rebuild a clean DB.

### AES-CBC Snap Decryption (Both Platforms)

Snap files downloaded from CDN are AES-CBC encrypted. Key and IV come from the database:
- **iOS**: `snap_key_iv.key` / `snap_key_iv.iv` (raw bytes → hex string)
- **Android**: `memories_snap.media_key` / `memories_snap.media_iv` (base64-encoded)

Output extension is determined by `format` field: `image_jpeg` → `.jpeg`, `video_hevc` / `video_avc` → `.mp4`.

### Case Output Folder Structure

```
<output_path>/
└── <case_name>/
    ├── scdb-*.sqlite3             # iOS: copied SCDB
    ├── gallery.encrypteddb        # iOS: original encrypted gallery
    ├── gallery.decrypted.sqlite   # iOS: decrypted (raw)
    ├── gallery.recovered.sqlite   # iOS: repaired clean DB
    ├── database.csv               # iOS + Android: snap metadata export
    ├── memories*.db               # Android: copied memories DB
    └── snaps/                     # Optional: downloaded + decrypted media
```

---

## External Integrations

| Integration       | Purpose                              | Config Location          |
| ----------------- | ------------------------------------ | ------------------------ |
| Snapchat CDN URLs | Download snap media files            | URLs stored in databases |
| UFED extractions  | Source of device data (zip → folder) | `Testing Data/`          |

---

## Maintenance

### When to Update This File

- New parser module added under `parsers/`
- New output artifact type introduced
- New dependency added to `requirements.txt`
- Decryption algorithm changes

### Verification Commands

```powershell
# Verify structure
tree G:\Github\Forensic-Snapchat-Parser /F /A

# Check dependencies
cat requirements.txt

# List parser modules
ls parsers\
```

---

> **Note**: This document is a navigation aid. Keep it accurate but don't over-document. Update when architecture changes, not for every file addition.
