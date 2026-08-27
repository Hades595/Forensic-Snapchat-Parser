def snap_in_date_range(capture_time: str | None, date_from: str | None, date_to: str | None) -> bool:
    """Return True if capture_time falls within [date_from, date_to] (inclusive, whole-day).

    capture_time is always formatted "YYYY-MM-DD HH:MM:SS UTC" (ISO-sortable), so the
    comparison is done on the date portion as a plain string. date_from/date_to are
    "YYYY-MM-DD" strings, or None when that bound isn't set.

    When no filter is active (both bounds None), always returns True. When a filter is
    active and capture_time is unknown, returns False — an unverifiable date is skipped.
    """
    if not date_from and not date_to:
        return True
    cap_date = (capture_time or "")[:10]
    if not cap_date:
        return False
    if date_from and cap_date < date_from:
        return False
    if date_to and cap_date > date_to:
        return False
    return True
