import os
import jinja2
from collections import defaultdict
from datetime import datetime, timezone


def _group_and_sort_chats(chats: list, conv_titles: dict = None) -> list:
    """Group messages by conversation and sort by most recent activity first.

    conv_titles: optional {conv_id: {"title": str|None, "type": int|None}} from feed_entry.
    """
    groups = defaultdict(list)
    for msg in chats:
        groups[msg["conversation_id"]].append(msg)

    conversations = []
    for conv_id, messages in groups.items():
        latest_ts_ms = max((m["timestamp_ms"] or 0) for m in messages)

        seen: set = set()
        participants: list = []
        for msg in messages:
            label = msg.get("sender_name") or msg.get("sender_id") or ""
            if label and label not in seen:
                seen.add(label)
                participants.append(label)

        sender_order = {label: idx for idx, label in enumerate(participants)}
        for msg in messages:
            label = msg.get("sender_name") or msg.get("sender_id") or ""
            msg["sender_index"] = sender_order.get(label, 0)

        feed = (conv_titles or {}).get(conv_id, {})
        conversations.append({
            "conversation_id": conv_id,
            "message_count":   len(messages),
            "latest_ts_ms":    latest_ts_ms,
            "participants":    participants,
            "messages":        messages,
            "title":           feed.get("title"),
            "conv_type":       feed.get("type"),
        })

    # Most recently active conversation first
    conversations.sort(key=lambda c: -c["latest_ts_ms"])
    return conversations


def _utc_str_to_local(utc_str: str) -> str | None:
    """Convert a 'YYYY-MM-DD HH:MM:SS UTC' string to the system's local time.

    The timezone suffix is abbreviated: Windows full names such as
    'New Zealand Standard Time' are reduced to their initials ('NZST').
    Already-short names (UTC, EST, GMT+12, …) are kept as-is.
    """
    if not utc_str:
        return None
    try:
        dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone()
        tz_name = local_dt.strftime("%Z").strip()
        # Abbreviate Windows-style full names (e.g. "New Zealand Standard Time" → "NZST")
        if len(tz_name) > 6 and " " in tz_name:
            tz_name = "".join(w[0].upper() for w in tz_name.split())
        return local_dt.strftime(f"%Y-%m-%d %H:%M:%S {tz_name}")
    except Exception:
        return None


def generate_report(
    case_name: str,
    snaps: list,
    chats: list,
    snap_sources: list,
    chat_sources: list,
    output_path: str,
    examiner: str = "",
    friends: list = None,
    snap_records: list = None,
    stories: list = None,
    user_profile: dict = None,
    conv_titles: dict = None,
) -> str:
    template_dir = os.path.join(os.path.dirname(__file__), "..", "html")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
    template = env.get_template("report_template.html")

    processed_snaps = []
    for snap in snaps:
        s = snap.copy()
        if s.get("file_path"):
            s["file_path"] = os.path.relpath(s["file_path"], output_path).replace(os.sep, "/")
        s["capture_time_local"] = _utc_str_to_local(s.get("capture_time"))
        processed_snaps.append(s)

    processed_snaps.sort(key=lambda s: s.get("capture_time") or "", reverse=True)

    # snap_id → relativized snap dict; lets template resolve snap previews in chat rows
    snap_ref_lookup = {s["snap_id"]: s for s in processed_snaps if s.get("snap_id")}

    # Friends with a known "added" date, excluding the epoch-zero placeholder value
    friends_added = [
        f for f in (friends or [])
        if f.get("added") and f["added"] != "1970-01-01 00:00:00 UTC"
    ]
    stories_named = [s for s in (stories or []) if s.get("display_name")]

    html = template.render(
        case_name=case_name,
        examiner=examiner,
        platform="Android",
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        snap_count=len(processed_snaps),
        snaps=processed_snaps,
        chat_count=len(chats),
        conversations=_group_and_sort_chats(chats, conv_titles=conv_titles),
        snap_sources=snap_sources,
        chat_sources=chat_sources,
        snap_ref_lookup=snap_ref_lookup,
        friends=friends_added,
        snap_records=snap_records or [],
        stories=stories_named,
        user_profile=user_profile or {},
    )

    report_path = os.path.join(output_path, "forensic_report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    return report_path
