#!/usr/bin/env python3
"""
Fetch and detect schedule posts from Instagram venue profiles.

Usage:
    python3 fetch-instagram.py                    # Fetch and detect schedules
    python3 fetch-instagram.py --list             # List cached schedule images
    python3 fetch-instagram.py --show             # Show paths to schedule images
    python3 fetch-instagram.py --status           # Show cache status
    python3 fetch-instagram.py --events           # Show extracted events
    python3 fetch-instagram.py --clear            # Clear cache
"""
import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add script directory to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from sources.instagram import InstagramSource


# Configured Instagram profiles
PROFILES = {
    "paradisoubud": {
        "name": "Paradiso Ubud",
        "schedule_detector": "maroon_template",
    },
}


async def main():
    parser = argparse.ArgumentParser(description="Fetch Instagram venue schedules")
    parser.add_argument("--list", action="store_true", help="List cached schedule images")
    parser.add_argument("--show", action="store_true", help="Show paths to schedule images for OCR")
    parser.add_argument("--status", action="store_true", help="Show cache status")
    parser.add_argument("--events", action="store_true", help="Show extracted events from cache")
    parser.add_argument("--clear", action="store_true", help="Clear image cache")
    parser.add_argument("--profile", type=str, help="Specific profile to fetch")
    parser.add_argument("--cached", action="store_true", help="Use cached results if available")
    parser.add_argument("--max-age", type=int, default=24, help="Max cache age in hours (default: 24)")
    args = parser.parse_args()
    
    source = InstagramSource(PROFILES)
    
    if not source.is_available():
        print("Error: instaloader not installed. Run: pipx install instaloader")
        sys.exit(1)
    
    if args.clear:
        source.clear_cache()
        print("Cache cleared.")
        return
    
    profiles_to_check = PROFILES
    if args.profile:
        if args.profile in PROFILES:
            profiles_to_check = {args.profile: PROFILES[args.profile]}
        else:
            print(f"Unknown profile: {args.profile}")
            sys.exit(1)
    
    if args.status:
        # Show cache status
        for username, config in profiles_to_check.items():
            manifest = source._load_manifest(username)
            print(f"\n@{username} ({config['name']}):")
            
            last_fetch = manifest.get("last_fetch")
            if last_fetch:
                try:
                    dt = datetime.fromisoformat(last_fetch)
                    age = datetime.now() - dt
                    print(f"  Last fetch: {dt.strftime('%Y-%m-%d %H:%M')} ({age.total_seconds()/3600:.1f}h ago)")
                except:
                    print(f"  Last fetch: {last_fetch}")
            else:
                print("  Last fetch: Never")
            
            images = manifest.get("images_fetched", [])
            schedules = manifest.get("detected_schedules", [])
            events = manifest.get("extracted_events", [])
            
            print(f"  Cached images: {len(images)}")
            print(f"  Detected schedules: {len(schedules)}")
            print(f"  Extracted events: {len(events)}")
            
            if manifest.get("events_extracted_at"):
                print(f"  Events extracted: {manifest['events_extracted_at']}")
        return
    
    if args.events:
        # Show extracted events
        for username, config in profiles_to_check.items():
            events = source.get_extracted_events(username)
            print(f"\n@{username} ({config['name']}) - {len(events)} events:")
            for event in events:
                print(f"  {event.get('day', '?')} {event.get('time', '')} - {event.get('name', 'Event')}")
        return
    
    if args.list or args.show:
        # Show cached schedule images
        for username, config in profiles_to_check.items():
            images = source.get_schedule_images(username)
            if images:
                print(f"\n@{username} ({config['name']}):")
                for img in images:
                    print(f"  {img}")
            else:
                print(f"\n@{username}: No cached schedule images")
        return
    
    # Fetch new posts and detect schedules
    print("Fetching recent posts from Instagram...")
    print("(This may take a moment, and may be rate-limited without login)\n")
    
    for username, config in profiles_to_check.items():
        print(f"@{username} ({config['name']}):")
        
        try:
            if args.cached:
                # Try to use cache first
                events = await source.fetch_events_cached(max_age_hours=args.max_age)
            else:
                # Fetch posts
                posts = await source._fetch_recent_posts(username, count=8)
                print(f"  Downloaded {len(posts)} posts")
                
                # Detect schedule posts
                schedules = [p for p in posts if source._is_schedule_post(p)]
                print(f"  Detected {len(schedules)} schedule posts:")
                
                for img in schedules:
                    print(f"    → {img}")
                
                if schedules:
                    print(f"\n  Latest schedule: {schedules[0]}")
                    print(f"  (View this image and ask me to extract the events)")
            
        except Exception as e:
            print(f"  Error: {e}")
        
        print()


if __name__ == "__main__":
    asyncio.run(main())
