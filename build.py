"""Fetch the public Humm Google Calendar, expand recurrences, write docs/events.json.
No API keys. Sensitive data (meeting links, passwords) is stripped."""
import json, re, sys, html, urllib.request, urllib.parse
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
import icalendar, recurring_ical_events

CAL_ID = "eu2ogb5h0us6vvcf94n050lo34@group.calendar.google.com"
URL = f"https://calendar.google.com/calendar/ical/{urllib.parse.quote(CAL_ID)}/public/basic.ics"
TZ = ZoneInfo("Europe/Tallinn")
HORIZON_DAYS = 365
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
ONLINE_RE = re.compile(r"zoom\.us|meet\.google|teams\.microsoft|jitsi|whereby", re.I)

def clean_text(s, limit=600):
    s = html.unescape(re.sub(r"<br\s*/?>", "\n", str(s or ""), flags=re.I))
    s = re.sub(r"<[^>]+>", "", s)
    s = re.split(r"(?i)[─\-_]{5,}|\S* ?is inviting you to a scheduled zoom meeting|join zoom meeting|liitu zoomi", s)[0]  # drop Zoom invitation boilerplate
    s = URL_RE.sub("", s)                      # never publish links from the calendar
    s = re.sub(r"(?i)\b(meeting id|passcode|password|parool|kood)\b[^\n]*", "", s)
    s = re.sub(r"[ \t]+", " ", s); s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s[:limit].rstrip()

def main(out="docs/events.json"):
    raw = urllib.request.urlopen(URL, timeout=30).read()
    cal = icalendar.Calendar.from_ical(raw)
    now = datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    events = []
    for ev in recurring_ical_events.of(cal).between(start, start + timedelta(days=HORIZON_DAYS)):
        if str(ev.get("STATUS", "")).upper() == "CANCELLED":
            continue
        ds, de = ev["DTSTART"].dt, (ev.get("DTEND").dt if ev.get("DTEND") else None)
        all_day = isinstance(ds, date) and not isinstance(ds, datetime)
        if all_day:
            s_iso, e_iso = ds.isoformat(), ((de - timedelta(days=1)).isoformat() if de else ds.isoformat())
        else:
            ds = ds.astimezone(TZ) if ds.tzinfo else ds.replace(tzinfo=TZ)
            de = (de.astimezone(TZ) if de.tzinfo else de.replace(tzinfo=TZ)) if de else ds
            if de < now: continue
            s_iso, e_iso = ds.isoformat(), de.isoformat()
        loc_raw = str(ev.get("LOCATION", "") or "")
        desc_raw = str(ev.get("DESCRIPTION", "") or "")
        online = bool(ONLINE_RE.search(loc_raw) or ONLINE_RE.search(desc_raw))
        loc = "" if URL_RE.search(loc_raw) else re.sub(r"\s*\n\s*", ", ", loc_raw).strip()
        events.append({
            "id": f"{ev.get('UID')}-{s_iso}",
            "series": str(ev.get("UID")),
            "title": clean_text(ev.get("SUMMARY", ""), 140),
            "start": s_iso, "end": e_iso, "allDay": all_day,
            "location": loc, "online": online,
            "description": clean_text(desc_raw),
            "recurring": bool(ev.get("RRULE") or ev.get("RECURRENCE-ID")),
        })
    events.sort(key=lambda e: e["start"])
    # series info so the site can show one line per recurring series
    by = {}
    for e in events: by.setdefault(e["series"], []).append(e)
    for group in by.values():
        for i, e in enumerate(group):
            e["seriesIndex"], e["seriesCount"], e["seriesLast"] = i, len(group), group[-1]["start"]
    payload = {"calendar": "Humm", "timezone": "Europe/Tallinn", "events": events}
    blob = json.dumps(payload, ensure_ascii=False, indent=1)
    assert "zoom.us" not in blob and "pwd=" not in blob, "sensitive link leaked"
    try:
        old = json.load(open(out)); old.pop("generated", None)
        if old == payload: print("unchanged", len(events)); return
    except Exception: pass
    payload["generated"] = now.isoformat(timespec="minutes")
    open(out, "w").write(json.dumps(payload, ensure_ascii=False, indent=1))
    print("written", len(events))

if __name__ == "__main__":
    main(*sys.argv[1:])
