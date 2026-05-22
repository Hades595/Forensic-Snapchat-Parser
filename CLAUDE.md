# Forensic Snapchat Parser

A desktop GUI tool for forensic analysis of Snapchat data extracted from iOS and Android devices via UFED.

**ALWAYS RESPOND IN ENGLISH**

## 📋 Core Working Principles

1. For maximum efficiency, whenever you need to perform multiple independent operations, invoke all relevant tools simultaneously and in parallel.
2. Before you finish, please verify your solution
3. Do what has been asked; nothing more, nothing less.
4. NEVER create files unless they're absolutely necessary for achieving your goal.
5. ALWAYS prefer editing an existing file to creating a new one.
6. NEVER proactively create documentation files (\*.md) or README files. Only create documentation files if explicitly requested by the User.

## 🏗️ Project Stack

- **Python** - core language, no build step
- **PySide6** - Qt GUI framework
- **qt-material** - Material Design stylesheet for Qt
- **PyCryptodome** - AES-CBC decryption of Snapchat media and databases
- **sqlite3** - stdlib, used to query Snapchat SQLite databases
- **plistlib** - stdlib, used to parse iOS keychain plist files
- **wget** - optional snap file downloads

## 🏛️ Architectural Principles

**"As simple as possible, but not simpler"**

- **KISS + DRY + YAGNI + Occam's Razor**: each new entity must justify its existence
- **Prior-art first**: look for existing solutions first, then write our own
- **No premature optimization**
- **100% certainty**: evaluate cascading effects before changes

## 🚨 Code Quality Standards

**All code checks are mandatory - code must be ✅ CLEAN!**
No errors. No formatting issues. No compiler warnings.

## 🎯 Main Project Features

1. **iOS parsing** — Decrypt `gallery.encrypteddb` with keychain-extracted AES key, parse SCDB, export CSV with snap metadata
2. **Android parsing** — Query `memories.db`, export snap metadata with encryption keys
3. **Snap download & decrypt** — Optionally download snaps from CDN URLs and AES-CBC decrypt them to JPEG/MP4

## 🏗️ Architectural Patterns

### Main Processing Flow

```
Select folder → Detect platform (UUID = iOS, com.snapchat.android = Android)
  → iOS:     parse keychain → decrypt gallery DB → parse SCDB → export CSV → [download snaps]
  → Android: parse memories.db → export metadata → [download & decrypt snaps]
```

### Module Layout

- **`main.py`** — `SnapchatParserGUI` (PySide6 widget), platform detection, orchestration
- **`parsers/ios/keychain.py`** — extracts `egocipher.key.avoidkeyderivation` from iOS keychain plist
- **`parsers/ios/ios.py`** — decrypts `gallery.encrypteddb`, repairs SQLite, parses SCDB, downloads/decrypts snaps
- **`parsers/android/android.py`** — queries `memories.db`, downloads/decrypts snaps
- **`parsers/html/report_template.html`** — Jinja2-style HTML report template
- **`parsers/sql/`** — SQL query files for reference

## 📁 Project Structure

```
Forensic-Snapchat-Parser/
  main.py                          # GUI entry point
  parsers/
    ios/
      ios.py                       # iOS parser (decrypt, query, export)
      keychain.py                  # Keychain AES key extractor
    android/
      android.py                   # Android parser
    html/
      report_template.html         # HTML report template
    sql/                           # Reference SQL queries
  requirements.txt
  logo.png
  Testing Data/                    # UFED extraction samples (not committed)
```

## 💻 Coding Standards

### FORBIDDEN:

- **NO hardcoded values** - use constants and configs!
- **NO code duplication** - reuse components and utilities!
- **NO ignoring errors** - handle all exceptions!
- **NO TODOs** in final code

### Mandatory rules:

- Meaningful names for variables and functions
- Early returns to reduce nesting
- Error handling explicit and clear

## 🛠️ Development Commands

### Main commands

- `python main.py` - Launch the GUI
- `pip install -r requirements.txt` - Install dependencies

### Dependencies not in requirements.txt (install manually if needed)

- `pycryptodome` — `pip install pycryptodome`
- `wget` — `pip install wget`

---

# Important Instructions Reminders

Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (\*.md) or README files. Only create documentation files if explicitly requested by the User.
