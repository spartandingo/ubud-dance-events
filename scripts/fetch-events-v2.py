#!/usr/bin/env python3
"""
Fetch and deduplicate embodied practice events from multiple sources.

Usage:
    python3 fetch-events-v2.py [--days N] [--json] [--region REGION] [--category CAT]

Examples:
    python3 fetch-events-v2.py                         # All sources, last 7 days
    python3 fetch-events-v2.py --days 14               # Last 14 days
    python3 fetch-events-v2.py --region ubud           # Ubud only
    python3 fetch-events-v2.py --category dance        # Dance events only
    python3 fetch-events-v2.py --region bali --category rope  # Bali rope events
    python3 fetch-events-v2.py --json                  # JSON output
    python3 fetch-events-v2.py --sources telegram      # Telegram only
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add script directory to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(script_dir.parent / ".env")

from sources.base import RawEvent
from sources.whatsapp import WhatsAppSource
from sources.telegram import TelegramSource
from sources.aggregator import EventAggregator

# Try to import website source
try:
    from sources.website import WebsiteSource
    WEBSITE_AVAILABLE = True
except ImportError:
    WEBSITE_AVAILABLE = False


def load_config() -> dict:
    """Load configuration from config.json."""
    config_path = script_dir.parent / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


def get_search_terms(config: dict, category: str = None) -> list[str]:
    """Get search terms, optionally filtered by category."""
    categories_config = config.get("categories", {})
    
    if category and category in categories_config:
        # Use category-specific search terms
        return categories_config[category].get("search_terms", [])
    
    # Combine all category search terms
    all_terms = set()
    for cat_config in categories_config.values():
        all_terms.update(cat_config.get("search_terms", []))
    
    return list(all_terms) if all_terms else None


def create_aggregator(config: dict, enabled_sources: set[str] = None) -> EventAggregator:
    """Create aggregator with configured sources."""
    aggregator = EventAggregator()
    
    # WhatsApp
    wa_config = config.get("whatsapp", {})
    if wa_config.get("enabled", True) and (enabled_sources is None or "whatsapp" in enabled_sources):
        groups = wa_config.get("groups", {})
        if groups:
            aggregator.add_source(WhatsAppSource(groups))
    
    # Telegram
    tg_config = config.get("telegram", {})
    if tg_config.get("enabled", True) and (enabled_sources is None or "telegram" in enabled_sources):
        groups = tg_config.get("groups", {})
        if groups:
            aggregator.add_source(TelegramSource(groups))
    
    # Websites
    if WEBSITE_AVAILABLE:
        web_config = config.get("websites", {})
        if web_config.get("enabled", True) and (enabled_sources is None or "website" in enabled_sources):
            sites = web_config.get("sites", {})
            if sites:
                aggregator.add_source(WebsiteSource(sites))
    
    return aggregator


def format_event_text(event: RawEvent) -> str:
    """Format a single event for terminal output."""
    lines = [f"**{event.event_name}**"]
    
    if event.event_date:
        date_line = f"  📅 {event.event_date}"
        if event.event_time:
            date_line += f" @ {event.event_time}"
        lines.append(date_line)
    
    if event.location:
        lines.append(f"  📍 {event.location}")
    
    if event.ticket_link:
        lines.append(f"  🎟️ {event.ticket_link}")
    
    # Show region and categories
    tags = []
    if event.region:
        tags.append(f"[{event.region}]")
    if event.categories:
        tags.extend(f"#{cat}" for cat in event.categories)
    
    source_line = f"  (from {event.source_name} via {event.source_type})"
    if tags:
        source_line += f" {' '.join(tags)}"
    lines.append(source_line)
    
    return "\n".join(lines)


def events_to_json(events: list[RawEvent]) -> list[dict]:
    """Convert events to JSON-serializable dicts."""
    return [
        {
            "event_name": e.event_name,
            "event_date": e.event_date,
            "event_time": e.event_time,
            "location": e.location,
            "ticket_link": e.ticket_link,
            "source_type": e.source_type,
            "source_name": e.source_name,
            "region": e.region,
            "categories": e.categories,
            "timestamp": e.timestamp.isoformat(),
            "text": e.text[:500],  # Truncate for readability
        }
        for e in events
    ]


def list_regions_and_categories(config: dict):
    """Print available regions and categories."""
    print("\n📍 Regions:")
    for region_id, region_data in config.get("regions", {}).items():
        name = region_data.get("name", region_id)
        tz = region_data.get("timezone", "")
        print(f"  {region_id}: {name} ({tz})")
    
    print("\n🏷️ Categories:")
    for cat_id, cat_data in config.get("categories", {}).items():
        name = cat_data.get("name", cat_id)
        terms = cat_data.get("search_terms", [])[:5]
        print(f"  {cat_id}: {name}")
        if terms:
            print(f"      terms: {', '.join(terms)}...")


async def main():
    parser = argparse.ArgumentParser(description="Fetch embodied practice events from multiple sources")
    parser.add_argument("--days", type=int, default=7, help="Days to look back (default: 7)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--sources", type=str, help="Comma-separated list of sources (whatsapp,telegram)")
    parser.add_argument("--region", type=str, help="Filter by region (ubud, bali, northern-rivers)")
    parser.add_argument("--category", type=str, help="Filter by category (dance, tantra, rope)")
    parser.add_argument("--status", action="store_true", help="Show source availability status")
    parser.add_argument("--list", action="store_true", help="List available regions and categories")
    args = parser.parse_args()
    
    config = load_config()
    
    # List mode
    if args.list:
        list_regions_and_categories(config)
        return
    
    # Get search terms based on category filter
    search_terms = get_search_terms(config, args.category)
    
    # Parse enabled sources
    enabled_sources = None
    if args.sources:
        enabled_sources = set(s.strip().lower() for s in args.sources.split(","))
    
    aggregator = create_aggregator(config, enabled_sources)
    
    # Status check
    if args.status:
        stats = aggregator.get_source_stats()
        print("Source Status:")
        for source, info in stats.items():
            status = "✅ available" if info["available"] else "❌ not available"
            print(f"  {source}: {status}")
        list_regions_and_categories(config)
        return
    
    # Build title
    title_parts = ["Embodied Events"]
    if args.region:
        regions = config.get("regions", {})
        region_name = regions.get(args.region, {}).get("name", args.region)
        title_parts.append(f"in {region_name}")
    if args.category:
        categories = config.get("categories", {})
        cat_name = categories.get(args.category, {}).get("name", args.category)
        title_parts.append(f"({cat_name})")
    
    title = " ".join(title_parts)
    
    # Fetch events
    print(f"Fetching events from last {args.days} days...", file=sys.stderr)
    if args.region:
        print(f"  Region: {args.region}", file=sys.stderr)
    if args.category:
        print(f"  Category: {args.category}", file=sys.stderr)
    
    events = await aggregator.fetch_all(
        days=args.days,
        search_terms=search_terms if not args.category else None,  # Skip search terms when category filtering
        region=args.region,
        category=args.category
    )
    
    if args.json:
        print(json.dumps(events_to_json(events), indent=2))
    else:
        print(f"\n=== {title} (last {args.days} days) ===\n")
        print(f"Found {len(events)} unique events\n")
        
        for event in events:
            print(format_event_text(event))
            print()


if __name__ == "__main__":
    asyncio.run(main())
