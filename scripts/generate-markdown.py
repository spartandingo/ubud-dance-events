#!/usr/bin/env python3
"""
Generate a nicely formatted markdown calendar from events.
"""
import json
import sys
import re
from datetime import datetime, timedelta
from pathlib import Path

def parse_event_date(date_str: str, reference_date: datetime) -> datetime | None:
    """Try to parse an event date string into a datetime."""
    if not date_str:
        return None
    
    date_str = date_str.lower().strip()
    
    # Month mapping
    months = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'sept': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12,
    }
    
    # Try "25 jan" or "jan 25" patterns
    for month_name, month_num in months.items():
        # "25 jan" or "25th jan"
        match = re.search(rf'(\d{{1,2}})(?:st|nd|rd|th)?\s*{month_name}', date_str)
        if match:
            day = int(match.group(1))
            year = reference_date.year
            # Check for year in string
            year_match = re.search(r'20\d{2}', date_str)
            if year_match:
                year = int(year_match.group())
            try:
                return datetime(year, month_num, day)
            except ValueError:
                continue
        
        # "jan 25" or "jan 25th"  
        match = re.search(rf'{month_name}\s*(\d{{1,2}})', date_str)
        if match:
            day = int(match.group(1))
            year = reference_date.year
            year_match = re.search(r'20\d{2}', date_str)
            if year_match:
                year = int(year_match.group())
            try:
                return datetime(year, month_num, day)
            except ValueError:
                continue
    
    return None


def clean_event_name(name: str) -> str:
    """Clean up event name."""
    # Remove telegram user links
    name = re.sub(r'\[([^\]]+)\]\(tg://user\?id=\d+\)', r'\1', name)
    # Remove markdown formatting
    name = re.sub(r'\*+', '', name)
    name = re.sub(r'_+', '', name)
    # Clean up whitespace
    name = ' '.join(name.split())
    return name.strip()


def main():
    # Read events from stdin or file
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            events = json.load(f)
    else:
        events = json.load(sys.stdin)
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today
    week_end = today + timedelta(days=7)
    
    # Parse and filter events for this week
    week_events = []
    for event in events:
        event_date = parse_event_date(event.get('event_date', ''), today)
        if event_date and week_start <= event_date <= week_end:
            event['parsed_date'] = event_date
            week_events.append(event)
    
    # Sort by date
    week_events.sort(key=lambda e: e['parsed_date'])
    
    # Group by day
    days = {}
    for event in week_events:
        day_key = event['parsed_date'].strftime('%A, %B %d')
        if day_key not in days:
            days[day_key] = []
        days[day_key].append(event)
    
    # Generate markdown
    lines = [
        f"# Ubud Dance Events",
        f"*Week of {week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}*",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
    ]
    
    if not days:
        lines.append("No events found for this week.")
    
    for day, day_events in days.items():
        lines.append(f"## {day}")
        lines.append("")
        
        for event in day_events:
            name = clean_event_name(event.get('event_name', 'Event'))
            time = event.get('event_time', '')
            location = event.get('location', '')
            ticket = event.get('ticket_link', '')
            source = event.get('source_name', '')
            
            lines.append(f"### {name}")
            
            details = []
            if time:
                details.append(f"🕐 {time}")
            if location:
                details.append(f"📍 {location}")
            if details:
                lines.append(" • ".join(details))
            
            if ticket and 'http' in ticket:
                # Clean up malformed URLs
                ticket = re.sub(r'\)+$', '', ticket)
                ticket = re.sub(r'\*+$', '', ticket)
                lines.append(f"🎟️ [Tickets]({ticket})")
            
            lines.append(f"*via {source}*")
            lines.append("")
        
        lines.append("---")
        lines.append("")
    
    print("\n".join(lines))


if __name__ == "__main__":
    main()
