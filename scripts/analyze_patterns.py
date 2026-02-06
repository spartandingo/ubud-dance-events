#!/usr/bin/env python3
"""
Analyze message history to identify recurring events.

Looks for patterns like:
- Same event name appearing multiple weeks
- Same day/time combinations
- Same venue on same weekday

Outputs a recurring_events.json that can be used to generate placeholders.
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Optional

# Day name mappings
DAY_NAMES = {
    0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
    4: "Friday", 5: "Saturday", 6: "Sunday"
}
DAY_ABBREV = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6
}

# Known venues with location info
VENUES = {
    "paradiso": {"name": "Paradiso", "address": "Ubud"},
    "moksa": {"name": "Moksa Ubud", "address": "Ubud"},
    "nalanda": {"name": "Nalanda", "address": "Ubud"},
    "amrtasiddhi": {"name": "AmrtaSiddhi", "address": "Ubud"},
    "sayuri": {"name": "Sayuri Healing Food", "address": "Ubud"},
}

# Event name patterns to normalize
EVENT_PATTERNS = [
    (r"contact\s*dojo\s*jam", "Contact Dojo Jam"),
    (r"contact\s*dojo\s*class", "Dojo Contact Class"),
    (r"dojo\s*contact\s*class", "Dojo Contact Class"),
    (r"dance\s*temple", "Dance Temple"),
    (r"5\s*rhythms", "5Rhythms"),
    (r"five\s*rhythms", "5Rhythms"),
    (r"resonanz", "Resonanz"),
    (r"ecstatic\s*dance", "Ecstatic Dance"),
    (r"dissolve.*play", "Dissolve & Play"),
    (r"dissolve.*eros", "Dissolve :: Eros"),
    (r"dissolve.*skills", "Dissolve CI Skills Lab"),
    (r"kinetic", "Kinetic CI Class"),
    (r"entropic", "ENTROPIC"),
    (r"ci\s*jam", "CI Jam"),
    (r"contact\s*jam", "Contact Jam"),
    (r"polina.*jam", "Saturday Polina CI Jam"),
    (r"round\s*robin", "Round Robin Jam"),
    (r"focus\s*jam", "CI Focus Jam"),
    (r"embodied\s*frequencies", "Embodied Frequencies"),
    (r"antidote", "Antidote"),
]


def normalize_event_name(text: str) -> Optional[str]:
    """Try to identify a known event name from text."""
    text_lower = text.lower()
    for pattern, name in EVENT_PATTERNS:
        if re.search(pattern, text_lower):
            return name
    return None


def extract_time(text: str) -> Optional[str]:
    """Extract time from text like '6pm', '6:00pm', '18:00'."""
    # Match patterns like "6pm", "6:00pm", "6.00pm", "18:00"
    patterns = [
        r'(\d{1,2})[:\.]?(\d{2})?\s*(am|pm)',  # 6pm, 6:00pm
        r'(\d{1,2}):(\d{2})\s*(?:am|pm)?',      # 18:00
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            hour = int(match.group(1))
            minute = match.group(2) or "00"
            if match.lastindex >= 3:
                meridiem = match.group(3)
                if meridiem == "pm" and hour < 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0
            return f"{hour:02d}:{minute}"
    
    return None


def extract_venue(text: str) -> Optional[dict]:
    """Extract venue from text."""
    text_lower = text.lower()
    for key, venue in VENUES.items():
        if key in text_lower:
            return venue
    return None


def extract_day(text: str) -> Optional[int]:
    """Extract day of week (0=Monday) from text."""
    text_lower = text.lower()
    for abbrev, day_num in DAY_ABBREV.items():
        if abbrev in text_lower:
            return day_num
    return None


def extract_price(text: str) -> Optional[str]:
    """Extract price from text like '150k', '150.000', 'IDR 150000'."""
    patterns = [
        r'(\d{2,3})\s*k\b',          # 150k
        r'(\d{2,3})[,.]?000\b',      # 150.000 or 150000
        r'idr\s*(\d+)',              # IDR 150000
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            amount = match.group(1)
            if len(amount) <= 3:
                return f"{amount}k"
            else:
                return f"{int(amount)//1000}k"
    return None


def analyze_message(msg: dict) -> list[dict]:
    """
    Analyze a message and extract any event mentions.
    Returns list of detected events.
    """
    text = msg.get("text", "")
    if len(text) < 30:
        return []
    
    events = []
    
    # Try to find an event name
    event_name = normalize_event_name(text)
    if not event_name:
        return []
    
    # Extract other details
    day = extract_day(text)
    time = extract_time(text)
    venue = extract_venue(text)
    price = extract_price(text)
    
    # If we found an event, record it
    events.append({
        "name": event_name,
        "day": day,
        "day_name": DAY_NAMES.get(day) if day is not None else None,
        "time": time,
        "venue": venue.get("name") if venue else None,
        "price": price,
        "source": msg.get("source"),
        "timestamp": msg.get("timestamp"),
    })
    
    return events


def find_recurring_events(events: list[dict]) -> list[dict]:
    """
    Analyze events to find recurring patterns.
    
    Returns list of recurring events with confidence scores.
    """
    # Group by event name + day
    by_name_day = defaultdict(list)
    for event in events:
        if event["name"] and event["day"] is not None:
            key = (event["name"], event["day"])
            by_name_day[key].append(event)
    
    recurring = []
    for (name, day), instances in by_name_day.items():
        if len(instances) >= 1:  # At least 1 mention
            # Find most common time and venue
            times = [e["time"] for e in instances if e["time"]]
            venues = [e["venue"] for e in instances if e["venue"]]
            prices = [e["price"] for e in instances if e["price"]]
            
            recurring.append({
                "name": name,
                "day": day,
                "day_name": DAY_NAMES[day],
                "time": max(set(times), key=times.count) if times else None,
                "venue": max(set(venues), key=venues.count) if venues else None,
                "price": max(set(prices), key=prices.count) if prices else None,
                "occurrences": len(instances),
                "confidence": min(len(instances) / 4, 1.0),  # 4+ mentions = 100%
                "sources": list(set(e["source"] for e in instances if e["source"])),
                "last_seen": max(e["timestamp"] for e in instances if e["timestamp"]),
            })
    
    # Sort by day then time
    recurring.sort(key=lambda x: (x["day"], x["time"] or ""))
    
    return recurring


def main():
    cache_dir = Path(__file__).parent.parent / ".cache"
    
    # Load message history
    all_messages = []
    
    wa_file = cache_dir / "whatsapp_30d.json"
    if wa_file.exists():
        with open(wa_file) as f:
            all_messages.extend(json.load(f))
        print(f"Loaded {len(all_messages)} WhatsApp messages")
    
    tg_file = cache_dir / "telegram_30d.json"
    if tg_file.exists():
        with open(tg_file) as f:
            tg_msgs = json.load(f)
            all_messages.extend(tg_msgs)
        print(f"Loaded {len(tg_msgs)} Telegram messages")
    
    if not all_messages:
        print("No messages found in cache. Run fetch first.")
        return
    
    # Analyze each message
    all_events = []
    for msg in all_messages:
        events = analyze_message(msg)
        all_events.extend(events)
    
    print(f"\nExtracted {len(all_events)} event mentions")
    
    # Find recurring patterns
    recurring = find_recurring_events(all_events)
    
    print(f"\nFound {len(recurring)} recurring events:\n")
    
    for event in recurring:
        conf = "✓" if event["confidence"] >= 0.75 else "?"
        time_str = event["time"] or "TBA"
        venue_str = event["venue"] or "TBA"
        price_str = event["price"] or ""
        
        print(f"{conf} {event['day_name']:9} {time_str:5} | {event['name']}")
        print(f"           @ {venue_str} {price_str}")
        print(f"           ({event['occurrences']} mentions, last: {event['last_seen'][:10] if event['last_seen'] else '?'})")
        print()
    
    # Save to file (separate from curated recurring_events.json)
    output_file = cache_dir / "detected_patterns.json"
    with open(output_file, "w") as f:
        json.dump(recurring, f, indent=2)
    print(f"Saved to {output_file}")


if __name__ == "__main__":
    main()
