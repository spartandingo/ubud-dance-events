"""
Event parser - extracts structured data from raw event text.
"""
import re
from typing import Optional
from .base import RawEvent


# Known venues with aliases
VENUES = {
    "paradiso": "Paradiso",
    "rasa ubud": "Rasa Ubud",
    "rasa yoga": "Rasa Ubud", 
    "yoga barn": "Yoga Barn",
    "the yoga barn": "Yoga Barn",
    "hidden space": "Hidden Space",
    "school of unified healing": "School of Unified Healing",
    "akasha": "Akasha",
    "pyramids of chi": "Pyramids of Chi",
    "taksu": "Taksu",
}


def parse_event_name(text: str) -> str:
    """Extract event name from message text."""
    # Look for *bold* text first (WhatsApp/Telegram formatting)
    match = re.search(r'\*([^*]+)\*', text)
    if match and len(match.group(1).strip()) > 3:
        return match.group(1).strip()[:60]
    
    # Look for **bold** (Markdown)
    match = re.search(r'\*\*([^*]+)\*\*', text)
    if match and len(match.group(1).strip()) > 3:
        return match.group(1).strip()[:60]
    
    # Otherwise use first meaningful line
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in lines[:3]:
        # Skip emoji-only or very short lines
        clean = re.sub(r'[^\w\s]', '', line)
        if len(clean.strip()) > 5:
            return line[:60]
    
    return "Event"


def parse_date(text: str) -> Optional[str]:
    """Extract event date from message text."""
    text_lower = text.lower()
    
    patterns = [
        # "22nd jan 2026", "jan 22nd", etc.
        r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:\s+\d{4})?)',
        r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*[-–,]\s*\d{1,2}(?:st|nd|rd|th)?)?(?:\s+\d{4})?)',
        # "Monday, Jan 22"
        r'((?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)[,\s]+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2})',
        # "22/01" or "22/01/2026"
        r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip()
    
    return None


def parse_time(text: str) -> Optional[str]:
    """Extract time from message text."""
    text_lower = text.lower()
    
    patterns = [
        r'(\d{1,2}[:\.]\d{2}\s*(?:am|pm)?)',
        r'(\d{1,2}\s*(?:am|pm))',
        r'@\s*(\d{1,2}[:\.]\d{2})',
        r'at\s+(\d{1,2}[:\.]\d{2})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip()
    
    return None


def parse_location(text: str) -> Optional[str]:
    """Extract venue/location from message text."""
    text_lower = text.lower()
    
    # Check known venues first
    for key, venue in VENUES.items():
        if key in text_lower:
            return venue
    
    # Try @ location pattern
    match = re.search(r'@\s*([^,\n@]+)', text)
    if match:
        loc = match.group(1).strip()
        if len(loc) > 3 and len(loc) < 50:
            return loc
    
    # Try "at [Venue]" pattern
    match = re.search(r'\bat\s+([A-Z][a-zA-Z\s]+?)(?:\s*[,.\n]|$)', text)
    if match:
        loc = match.group(1).strip()
        if len(loc) > 3 and len(loc) < 40:
            return loc
    
    return None


def parse_ticket_link(text: str) -> Optional[str]:
    """Extract ticket/registration link from message text."""
    # Priority: ticketing platforms
    ticket_patterns = [
        r'(https?://[^\s\n]*megatix[^\s\n]*)',
        r'(https?://[^\s\n]*humanitix[^\s\n]*)',
        r'(https?://[^\s\n]*eventbrite[^\s\n]*)',
        r'(https?://[^\s\n]*(?:ticket|register|book)[^\s\n]*)',
    ]
    
    for pattern in ticket_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # Fallback: any https link
    match = re.search(r'(https?://[^\s\n]+)', text)
    if match:
        url = match.group(1)
        # Skip common non-event links
        skip_domains = ['wa.me', 'whatsapp.com', 't.me', 'telegram.', 'instagram.', 'facebook.com/photo']
        if not any(d in url.lower() for d in skip_domains):
            return url
    
    return None


def parse_event(event: RawEvent) -> RawEvent:
    """Parse and enrich a raw event with extracted fields."""
    event.event_name = parse_event_name(event.text)
    event.event_date = parse_date(event.text)
    event.event_time = parse_time(event.text)
    event.location = parse_location(event.text)
    event.ticket_link = parse_ticket_link(event.text)
    return event
