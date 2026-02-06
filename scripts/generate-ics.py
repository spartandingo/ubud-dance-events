#!/usr/bin/env python3
"""
Generate ICS calendar file from Ubud dance events.

Creates a subscribable .ics feed with:
- Recurring weekly events (from recurring_events.json)
- One-off special events (from special_events.json if exists)

Usage: python3 generate-ics.py [--weeks N] [--output FILE]
"""
import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse

BALI_TZ = "Asia/Makassar"
CACHE_DIR = Path(__file__).parent.parent / ".cache"
OUTPUT_DIR = Path(__file__).parent.parent

# VTIMEZONE component for WITA (UTC+8)
VTIMEZONE = """BEGIN:VTIMEZONE
TZID:Asia/Makassar
X-LIC-LOCATION:Asia/Makassar
BEGIN:STANDARD
TZOFFSETFROM:+0800
TZOFFSETTO:+0800
TZNAME:WITA
DTSTART:19700101T000000
END:STANDARD
END:VTIMEZONE"""


def load_recurring_events() -> list[dict]:
    """Load recurring events database."""
    path = CACHE_DIR / "recurring_events.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)
            return data.get("weekly_schedule", [])
    return []


def load_special_events() -> list[dict]:
    """Load one-off special events."""
    path = CACHE_DIR / "special_events.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def get_week_mondays(weeks: int) -> list[datetime]:
    """Get Monday dates for the next N weeks."""
    today = datetime.now()
    # Start from this week's Monday
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(weeks=i) for i in range(weeks)]


def generate_uid(event: dict, date: datetime) -> str:
    """Generate stable UID for an event."""
    key = f"{event['name']}-{event.get('day', 0)}-{date.strftime('%Y%m%d')}"
    return hashlib.md5(key.encode()).hexdigest()[:16] + "@ubud-dance"


def escape_ics(text: str) -> str:
    """Escape text for ICS format."""
    if not text:
        return ""
    # ICS requires escaping backslash, semicolon, comma, and newlines
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\n", "\\n")
    return text


def format_time(time_str: str) -> str:
    """Convert HH:MM to HHMMSS."""
    if not time_str:
        return "000000"
    parts = time_str.split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return f"{h:02d}{m:02d}00"


def generate_vevent(event: dict, date: datetime) -> str:
    """Generate a VEVENT component."""
    uid = generate_uid(event, date)
    
    # Start time
    start_time = event.get("time") or "09:00"
    dtstart = date.strftime("%Y%m%d") + "T" + format_time(start_time)
    
    # End time
    end_time = event.get("end_time")
    if end_time:
        dtend = date.strftime("%Y%m%d") + "T" + format_time(end_time)
    else:
        # Default 2 hour duration
        parts = start_time.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        end_h = h + 2
        dtend = date.strftime("%Y%m%d") + f"T{end_h:02d}{m:02d}00"
    
    # Location
    venue = event.get("venue", "")
    location = f"{venue}, Ubud, Bali" if venue else "Ubud, Bali"
    
    # Description
    desc_parts = []
    if event.get("notes"):
        desc_parts.append(event["notes"])
    if event.get("price"):
        desc_parts.append(f"Price: {event['price']}")
    if event.get("url"):
        desc_parts.append(f"Info/Tickets: {event['url']}")
    if event.get("sources"):
        desc_parts.append(f"Source: {', '.join(event['sources'])}")
    
    # Status
    confidence = event.get("confidence", 0.8)
    if confidence >= 0.9:
        status = "CONFIRMED"
    elif confidence >= 0.7:
        status = "TENTATIVE"
    else:
        status = "TENTATIVE"
    
    description = escape_ics(" | ".join(desc_parts))
    summary = escape_ics(event["name"])
    location = escape_ics(location)
    
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    vevent = f"""BEGIN:VEVENT
UID:{uid}
DTSTAMP:{now}
DTSTART;TZID={BALI_TZ}:{dtstart}
DTEND;TZID={BALI_TZ}:{dtend}
SUMMARY:{summary}
LOCATION:{location}
DESCRIPTION:{description}
STATUS:{status}
CATEGORIES:Dance,Contact Improv,Ubud"""
    
    # Add URL if present
    if event.get("url"):
        vevent += f"\nURL:{event['url']}"
    
    vevent += "\nEND:VEVENT"
    
    return vevent


def generate_ics(weeks: int = 4) -> str:
    """Generate complete ICS calendar."""
    
    recurring = load_recurring_events()
    special = load_special_events()
    
    # Calendar header
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Ubud Dance Events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Ubud Dance Events",
        "X-WR-CALDESC:Contact improv, ecstatic dance, and movement events in Ubud, Bali",
        "X-WR-TIMEZONE:Asia/Makassar",
        VTIMEZONE,
    ]
    
    # Generate events for each week
    mondays = get_week_mondays(weeks)
    
    for monday in mondays:
        for event in recurring:
            day_offset = event.get("day", 0)  # 0=Monday
            event_date = monday + timedelta(days=day_offset)
            
            # Skip past events
            if event_date.date() < datetime.now().date():
                continue
            
            lines.append(generate_vevent(event, event_date))
    
    # Add special events
    for event in special:
        if "date" in event:
            try:
                event_date = datetime.strptime(event["date"], "%Y-%m-%d")
                if event_date.date() >= datetime.now().date():
                    lines.append(generate_vevent(event, event_date))
            except:
                pass
    
    lines.append("END:VCALENDAR")
    
    # ICS requires CRLF line endings
    return "\r\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate ICS calendar for Ubud dance events")
    parser.add_argument("--weeks", type=int, default=4, help="Number of weeks to generate (default: 4)")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    args = parser.parse_args()
    
    print(f"Generating calendar for {args.weeks} weeks...")
    
    recurring = load_recurring_events()
    special = load_special_events()
    print(f"  {len(recurring)} recurring events")
    print(f"  {len(special)} special events")
    
    ics_content = generate_ics(weeks=args.weeks)
    
    # Output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = OUTPUT_DIR / "docs" / "ubud-dance-events.ics"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        f.write(ics_content)
    
    print(f"\nSaved to {output_path}")
    print(f"\nTo subscribe in Apple Calendar:")
    print(f"  1. File → New Calendar Subscription")
    print(f"  2. Enter the URL where you host this file")


if __name__ == "__main__":
    main()
