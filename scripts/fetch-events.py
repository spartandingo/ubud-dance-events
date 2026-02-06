#!/usr/bin/env python3
"""
Fetch and deduplicate dance events from Ubud WhatsApp groups.
Usage: python3 fetch-events.py [--days N] [--json]
"""

import subprocess
import json
import re
import sys
from datetime import datetime, timedelta
from collections import defaultdict
import argparse
import hashlib

# Source group JIDs
GROUPS = {
    "17609142454-1609066274@g.us": "Sayuri Academy",
    "6281338201923-1627265153@g.us": "Ubud Events 1",
    "120363324641442334@g.us": "Ubud Events 2",
}

# Search terms
SEARCH_TERMS = ["dance", "ecstatic", "improv", "movement", "Paradiso", "RESONANZ", "workshop", "jam"]

def fetch_messages(group_jid: str, after_date: str, term: str) -> list:
    """Fetch messages from a group matching a search term."""
    try:
        result = subprocess.run(
            ["wacli", "messages", "search", term, 
             "--chat", group_jid, 
             "--after", after_date, 
             "--limit", "30", 
             "--json"],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(result.stdout)
        if data.get("success") and data.get("data", {}).get("messages"):
            return data["data"]["messages"]
    except Exception:
        pass
    return []

def extract_event_signature(text: str) -> str:
    """Create a signature for deduplication based on key event details."""
    # Normalize: lowercase, remove extra whitespace
    normalized = re.sub(r'\s+', ' ', text.lower().strip())
    # Extract first 200 chars for comparison
    return hashlib.md5(normalized[:200].encode()).hexdigest()

def parse_date_from_text(text: str) -> str | None:
    """Try to extract event date from message text."""
    patterns = [
        r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:\s+\d{4})?)',
        r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*[-–,]\s*\d{1,2}(?:st|nd|rd|th)?)?(?:\s+\d{4})?)',
        r'((?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)[,\s]+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2})',
        r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)',
    ]
    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip()
    return None

def extract_time(text: str) -> str | None:
    """Extract time from text."""
    patterns = [
        r'(\d{1,2}[:.]\d{2}\s*(?:am|pm)?)',
        r'(\d{1,2}\s*(?:am|pm))',
        r'(\d{1,2}:\d{2})',
    ]
    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip()
    return None

def extract_location(text: str) -> str | None:
    """Extract venue/location."""
    venues = ["Paradiso", "Rasa Ubud", "Yoga Barn", "Hidden Space", "School of Unified Healing"]
    text_lower = text.lower()
    for venue in venues:
        if venue.lower() in text_lower:
            return venue
    # Try to find @ location pattern
    match = re.search(r'@\s*([^,\n]+)', text)
    if match:
        return match.group(1).strip()[:50]
    return None

def extract_ticket_link(text: str) -> str | None:
    """Extract ticket/registration link."""
    match = re.search(r'(https?://[^\s\n]+(?:megatix|ticket|event|register)[^\s\n]*)', text, re.I)
    if match:
        return match.group(1)
    # Generic link as fallback
    match = re.search(r'(https?://megatix[^\s\n]+)', text)
    if match:
        return match.group(1)
    return None

def extract_event_name(text: str) -> str:
    """Try to extract event name from first line or bold text."""
    # Look for *bold* text first (WhatsApp formatting)
    match = re.search(r'\*([^*]+)\*', text)
    if match:
        return match.group(1).strip()[:60]
    # Otherwise use first meaningful line
    lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 3]
    if lines:
        # Skip emoji-only lines
        first = lines[0]
        if len(re.sub(r'[^\w\s]', '', first)) > 3:
            return first[:60]
    return "Event"

def main():
    parser = argparse.ArgumentParser(description='Fetch Ubud dance events')
    parser.add_argument('--days', type=int, default=7, help='Days to look back')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()
    
    after_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
    
    # Collect all messages
    all_messages = []
    seen_signatures = set()
    
    for jid, name in GROUPS.items():
        for term in SEARCH_TERMS:
            messages = fetch_messages(jid, after_date, term)
            for msg in messages:
                text = msg.get("Text", "")
                if not text or len(text) < 50:
                    continue
                
                sig = extract_event_signature(text)
                if sig in seen_signatures:
                    continue
                seen_signatures.add(sig)
                
                all_messages.append({
                    "group": name,
                    "jid": jid,
                    "timestamp": msg.get("Timestamp", ""),
                    "text": text,
                    "event_name": extract_event_name(text),
                    "event_date": parse_date_from_text(text),
                    "time": extract_time(text),
                    "location": extract_location(text),
                    "ticket_link": extract_ticket_link(text),
                })
    
    if args.json:
        print(json.dumps(all_messages, indent=2))
    else:
        print(f"=== Ubud Dance Events (last {args.days} days) ===\n")
        print(f"Found {len(all_messages)} unique events\n")
        
        for msg in sorted(all_messages, key=lambda x: x.get("event_date") or ""):
            print(f"**{msg['event_name']}**")
            if msg['event_date']:
                print(f"  📅 {msg['event_date']}", end="")
                if msg['time']:
                    print(f" @ {msg['time']}", end="")
                print()
            if msg['location']:
                print(f"  📍 {msg['location']}")
            if msg['ticket_link']:
                print(f"  🎟️ {msg['ticket_link']}")
            print(f"  (from {msg['group']})")
            print()

if __name__ == "__main__":
    main()
