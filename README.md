# Snapchat Forensic Parser

A desktop GUI tool for forensic analysis of Snapchat data extracted from iOS and Android devices.

---

## Features

- **iOS parsing** — Extracts the AES decryption key from an iOS keychain plist, decrypts `gallery.encrypteddb`, repairs the recovered SQLite database, then queries `scdb-*.sqlite3` to correlate snap metadata (capture time, GPS coordinates, media format, encryption key/IV)
- **Android parsing** — Queries `memories.db` directly (no decryption needed) to extract snap metadata including CDN download URLs and AES-CBC keys
- **Snap download & decrypt** — Optionally downloads snaps from CDN URLs and decrypts them to `.jpeg` or `.mp4`
- **HTML report** — Generates a formatted forensic report (`forensic_report.html`) that opens automatically on completion
- **CSV export** — Exports snap metadata (Snap ID, region, GPS, key, IV) to `database.csv`

---

## Requirements

**Python 3.10+**

Install dependencies:

```bash
pip install -r requirements.txt
pip install pycryptodome wget
```

`requirements.txt` covers `PySide6`, `qt-material`, and `jinja2`. `pycryptodome` and `wget` must be installed separately (see above).

---

## Usage

```bash
python main.py
```

### iOS workflow

1. **Snapchat Folder** — Select the UUID-named folder from the extraction (e.g. `A1B2C3D4-…-XXXXXXXXXXXX`)
2. **Keychain File** — Select the iOS keychain plist exported by
3. **Case Name / Examiner Name** — Enter case metadata
4. **Output Folder** — Select where results will be saved
5. *(Optional)* Check **Download Snaps** to pull and decrypt media files
6. Click **Process**

### Android workflow

1. **Snapchat Folder** — Select the `com.snapchat.android` folder from the extraction
2. **Case Name / Examiner Name** — Enter case metadata
3. **Output Folder** — Select where results will be saved
4. *(Optional)* Check **Download Snaps** to pull and decrypt media files
5. Click **Process**

The keychain field is automatically disabled for Android extractions.

---

## Output

For each case, a subfolder is created at `<output>/<case_name>/`:

| File | Description |
|---|---|
| `forensic_report.html` | Full HTML report (opens in browser automatically) |
| `database.csv` | Snap metadata: ID, region, GPS, key, IV |
| `gallery.encrypteddb` | Original encrypted gallery DB (iOS) |
| `gallery.decrypted.sqlite` | Decrypted gallery DB (iOS) |
| `gallery.recovered.sqlite` | Repaired gallery DB used for querying (iOS) |
| `scdb-*.sqlite3` | Copy of the snap cache DB (iOS) |
| `memories*.db` | Copy of the memories DB (Android) |
| `snaps/` | Downloaded & decrypted media files (if enabled) |

---

## Project Structure

```
Forensic-Snapchat-Parser/
  main.py                        # GUI entry point (PySide6)
  parsers/
    ios/
      ios.py                     # Decrypt gallery DB, parse SCDB, download snaps
      keychain.py                # Extract AES key from iOS keychain plist
      reporting.py               # HTML report generation (iOS)
    android/
      android.py                 # Parse memories.db, download snaps
      reporting.py               # HTML report generation (Android)
    html/
      report_template.html       # Jinja2 HTML report template
    sql/                         # Reference SQL queries
  requirements.txt
  logo.png
```

---

## Database Sources

### Android
**Root:** `com.snapchat.android/`

| Path | Data | Parsed |
|---|---|---|
| `databases/memories.db` | Snap memories — media URLs, AES keys/IVs, GPS coords, capture timestamps, duration, favourite/front-facing flags | ✅ |
| `databases/arroyo.db` | Chat messages, conversation IDs, sender IDs, timestamps, read/save state, protobuf message content, group names | ✅ |
| `databases/main.db` | Friends + scores (Friend × FriendScore), contact phone numbers, snap records, story records | ✅ |
| `databases/core.db` | User profile — username, full name, DOB, email, phone, locale, account UUID | ✅ |
| `databases/client_notifications.db` | Push notification history | ❌ |
| `databases/creativetools.platform.db` | Creative tools usage (filters, stickers applied to snaps) | ❌ |
| `databases/rtus.db` | Real-time update service — may contain notification/message history | ❌ |
| `databases/simple_db_helper.db` | Unknown — very large (~86 MB), likely media cache metadata | ❌ |
| `databases/{uuid}/contactscache.identity.db` | Cached contact identity data | ❌ |
| `databases/native_content_manager/cache_controller.db` | Media/content cache controller | ❌ |
| `databases/fidelius_database.db` | Encryption/authentication keys | ❌ |

### iOS
**Root:** `{DeviceUUID}/` (e.g. `182213FD-7993-4C96-BE7A-8EC70399100D/`)

| Path | Data | Parsed |
|---|---|---|
| `Documents/gallery_encrypted_db/<n>/<uid>/gallery.encrypteddb` | AES-CBC encrypted database — snap decryption keys/IVs, GPS coordinates, region names | ✅ |
| `Documents/gallery_data_object/<n>/<uid>/scdb-<n>.sqlite3` | Snap metadata — capture time UTC, duration, media download URLs, media format, gallery profile (user UUID) | ✅ |
| `Documents/user_scoped/<uid>/arroyo/arroyo.db` | Chat messages, conversation IDs, sender IDs, timestamps, read/save state, protobuf content, group names | ✅ |
| `Documents/friending_notification_snapchatter.db` | Friends list — userId, username, display name, contact origin, added timestamp, friend type | ✅ |
| `Library/Caches/SCCache/` | **Cleartext cached snaps** — previously viewed/received snaps, no decryption needed | ❌ |
| `Library/Caches/SCMediaCache/` | Cleartext cached media (stories, received snaps) | ❌ |
| `Library/Caches/SCPersistentMedia/` | Persistently cached media files | ❌ |
| `Documents/user_scoped/<uid>/databases/content_feed_database` | Cached story/Discover feed content | ❌ |
| `Documents/user_scoped/<uid>/DocObjects/primary.docobjects` | CloudKit document store — structured user-scoped object data (format unknown, high forensic value) | ❌ |
| `Documents/global_scoped/global-scoped-preferences/preferences.sqlite` | App preferences — session username and phone number keys (values are binary-serialised) | ❌ |
| `Documents/gallery_search/<n>/<uid>/search.sqlite3` | FTS index — snap descriptions, location tags, time tags | ❌ |
| `Documents/user_scoped/<uid>/databases/memories_asset_repository.sqlite` | Memories asset links — asset IDs, download URLs, encryption key/IV references | ❌ |
| `Documents/user_scoped/<uid>/databases/convo_safety.db` | Conversation safety flags — reported messages, moderation prompts | ❌ |
| `Documents/Valdi/sqlite/<uuid>/CallLog.db` | Voice/video call log — participants, timestamps, duration | ❌ |
| `Library/Application Support/fidelius_user_db/<n>/<uuid>/fidelius_user.db` | End-to-end encryption keys — identity keys, per-message keys, per-snap encryption keys | ❌ |

---

## Platform Detection

The tool detects the platform automatically from the selected folder name:

| Folder name pattern | Platform |
|---|---|
| `com.snapchat.android` | Android |
| UUID format (`XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`) | iOS |

---

## Dependencies

| Package | Purpose |
|---|---|
| `PySide6` | Qt6 GUI framework |
| `qt-material` | Material Design stylesheet |
| `jinja2` | HTML report templating |
| `pycryptodome` | AES-CBC decryption of Snapchat databases and media |
| `wget` | CDN snap downloads |
| `sqlite3` | stdlib — SQLite database queries |
| `plistlib` | stdlib — iOS keychain plist parsing |

---

## Disclaimer

This tool is intended for **lawful forensic examination only**. Use it only on devices and data for which you have explicit legal authorisation. The authors accept no liability for misuse.
