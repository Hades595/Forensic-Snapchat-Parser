import os
import re
import plistlib

_AES256_KEY_SIZE = 32   # bytes — the AES-256 key length
_HEX_KEY_RE = re.compile(r'^[0-9a-fA-F]{64}$')


def process_keychain(keychain_path: str) -> str:
    """Extract the AES-256 gallery decryption key from a UFED export.

    Accepts four forms of input:
    1. Raw 64-char hex string typed/pasted directly (not a file path)
    2. Raw 32-byte binary key file (ego.cipherkey)
    3. Text file containing a 64-char hex string (ego.cipherkey exported as text)
    4. Keychain plist (.plist) — standard UFED export

    Always returns a lowercase hex string on success, or a
    "Keychain processing failed: …" message on failure.
    """
    try:
        # ── 1. Direct hex string input (not a file path) ──────────────────
        stripped = keychain_path.strip()
        if _HEX_KEY_RE.match(stripped):
            return stripped.lower()

        # ── 2. File-based inputs ───────────────────────────────────────────
        file_size = os.path.getsize(keychain_path)

        if file_size == _AES256_KEY_SIZE:
            # Raw 32-byte binary key file
            with open(keychain_path, "rb") as f:
                return f.read().hex()

        if file_size in (_AES256_KEY_SIZE * 2, _AES256_KEY_SIZE * 2 + 1):
            # Text file with 64 hex chars (+ optional trailing newline)
            try:
                with open(keychain_path, "r", encoding="ascii", errors="strict") as f:
                    content = f.read().strip()
                if _HEX_KEY_RE.match(content):
                    return content.lower()
            except (UnicodeDecodeError, OSError):
                pass  # not a text file — fall through to plist

        # Standard UFED keychain plist
        with open(keychain_path, "rb") as f:
            plist = plistlib.load(f)
        for item in plist.get("genp", []):
            try:
                if item["gena"].decode("ASCII") == "egocipher.key.avoidkeyderivation":
                    return item["v_Data"].hex()
            except Exception:
                continue
        return "Keychain processing failed: egocipher.key.avoidkeyderivation not found in plist"

    except Exception as e:
        return f"Keychain processing failed: {e}"
