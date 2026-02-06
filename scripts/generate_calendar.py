#!/usr/bin/env python3
"""
Generate weekly event calendar markdown.

Uses:
1. Recurring events database (placeholders with "likely" status)
2. Confirmed events from recent messages
3. Instagram schedule images (confirmed)

Events are marked as:
- ✓ Confirmed - explicitly announced for this specific date
- ~ Likely - recurring event, no cancellation announced
- ? Tentative - one-off or unconfirmed
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

CACHE_DIR = Path(__file__).parent.parent / ".cache"
OUTPUT_DIR = Path(__file__).parent.parent


def load_recurring_events() -> list[dict]:
    """Load the recurring events database."""
    path = CACHE_DIR / "recurring_events.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)
            return data.get("weekly_schedule", [])
    return []


def get_week_dates(start_date: datetime = None, next_week: bool = False) -> list[datetime]:
    """Get dates for the current/next week (Mon-Sun)."""
    if start_date is None:
        start_date = datetime.now()
    
    # Find the Monday of this week
    monday = start_date - timedelta(days=start_date.weekday())
    
    # If next_week or we're past Thursday, show next week
    if next_week or start_date.weekday() >= 4:  # Friday onwards
        monday += timedelta(weeks=1)
    
    return [monday + timedelta(days=i) for i in range(7)]


def generate_placeholders(week_dates: list[datetime], recurring: list[dict]) -> list[dict]:
    """Generate placeholder events for the week based on recurring schedule."""
    events = []
    
    for event in recurring:
        day_idx = event["day"]  # 0=Monday
        event_date = week_dates[day_idx]
        
        events.append({
            "date": event_date,
            "day_name": event["day_name"],
            "time": event.get("time"),
            "end_time": event.get("end_time"),
            "name": event["name"],
            "venue": event.get("venue"),
            "price": event.get("price"),
            "notes": event.get("notes"),
            "status": "likely" if event.get("confidence", 0) >= 0.8 else "tentative",
            "sources": event.get("sources", []),
        })
    
    return events


def format_time(time_str: str, end_time: str = None) -> str:
    """Format time for display."""
    if not time_str:
        return "TBA"
    
    # Convert 24h to 12h format
    try:
        h, m = map(int, time_str.split(":"))
        suffix = "am" if h < 12 else "pm"
        h = h % 12 or 12
        start = f"{h}:{m:02d}{suffix}" if m else f"{h}{suffix}"
        
        if end_time:
            h2, m2 = map(int, end_time.split(":"))
            suffix2 = "am" if h2 < 12 else "pm"
            h2 = h2 % 12 or 12
            end = f"{h2}:{m2:02d}{suffix2}" if m2 else f"{h2}{suffix2}"
            return f"{start}–{end}"
        return start
    except:
        return time_str


def generate_markdown(events: list[dict], week_dates: list[datetime]) -> str:
    """Generate markdown calendar."""
    lines = []
    
    # Header
    start = week_dates[0]
    end = week_dates[6]
    lines.append(f"# Ubud Dance Events")
    lines.append(f"*Week of {start.strftime('%B %d')} – {end.strftime('%B %d, %Y')}*")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} WITA")
    lines.append("")
    lines.append("**Status:** ✓ Confirmed | ~ Likely (recurring) | ? Tentative")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Group events by date
    by_date = {}
    for event in events:
        date_key = event["date"].strftime("%Y-%m-%d")
        if date_key not in by_date:
            by_date[date_key] = []
        by_date[date_key].append(event)
    
    # Generate each day
    for date in week_dates:
        date_key = date.strftime("%Y-%m-%d")
        day_events = by_date.get(date_key, [])
        
        # Sort by time
        day_events.sort(key=lambda e: e.get("time") or "99:99")
        
        # Day header
        lines.append(f"## {date.strftime('%A, %B %d')}")
        lines.append("")
        
        if not day_events:
            lines.append("*No events scheduled*")
            lines.append("")
        else:
            for event in day_events:
                # Status indicator
                if event["status"] == "confirmed":
                    status = "✓"
                elif event["status"] == "likely":
                    status = "~"
                else:
                    status = "?"
                
                lines.append(f"### {status} {event['name']}")
                
                time_str = format_time(event.get("time"), event.get("end_time"))
                lines.append(f"🕐 {time_str}")
                
                if event.get("venue"):
                    lines.append(f"📍 {event['venue']}")
                
                if event.get("price"):
                    lines.append(f"💰 {event['price']}")
                
                if event.get("notes"):
                    lines.append(f"*{event['notes']}*")
                
                if event.get("sources"):
                    lines.append(f"*via {', '.join(event['sources'])}*")
                
                lines.append("")
        
        lines.append("---")
        lines.append("")
    
    # Weekly summary table
    lines.append("## Weekly Schedule (Recurring)")
    lines.append("")
    lines.append("| Day | Time | Event | Venue | Price |")
    lines.append("|-----|------|-------|-------|-------|")
    
    recurring = load_recurring_events()
    for event in recurring:
        time_str = format_time(event.get("time"))
        lines.append(
            f"| {event['day_name'][:3]} | {time_str} | {event['name']} | "
            f"{event.get('venue', 'TBA')} | {event.get('price', '–')} |"
        )
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*This calendar includes recurring events as placeholders. ")
    lines.append("Events marked with ~ are expected based on past patterns but not yet confirmed for this specific week.*")
    
    return "\n".join(lines)


def main():
    print("Generating weekly calendar...")
    
    # Load recurring events
    recurring = load_recurring_events()
    print(f"Loaded {len(recurring)} recurring events")
    
    # Get this week's dates
    week_dates = get_week_dates()
    print(f"Week: {week_dates[0].strftime('%Y-%m-%d')} to {week_dates[6].strftime('%Y-%m-%d')}")
    
    # Generate placeholder events
    events = generate_placeholders(week_dates, recurring)
    print(f"Generated {len(events)} placeholder events")
    
    # TODO: Merge with confirmed events from recent messages
    # TODO: Mark Instagram-sourced events as confirmed
    
    # Generate markdown
    markdown = generate_markdown(events, week_dates)
    
    # Write output
    output_path = OUTPUT_DIR / "events-this-week.md"
    with open(output_path, "w") as f:
        f.write(markdown)
    
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
