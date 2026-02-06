"""
Website event source - scrapes venue websites directly.
"""
import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

from .base import EventSource, RawEvent, GroupConfig

# Try to import aiohttp for async HTTP
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class WebsiteSource(EventSource):
    """Fetch events from venue websites."""
    
    source_type = "website"
    
    def __init__(self, sites_config: dict):
        """
        Args:
            sites_config: Dict mapping site ID -> config dict
        """
        self.sites = sites_config
    
    def is_available(self) -> bool:
        """Check if we can make HTTP requests."""
        return AIOHTTP_AVAILABLE
    
    async def fetch_events(
        self,
        days: int = 7,
        search_terms: list[str] = None,
        region: str = None,
        category: str = None
    ) -> list[RawEvent]:
        """Fetch events from configured websites."""
        if not self.is_available():
            print("Warning: aiohttp not available, skipping website sources")
            return []
        
        events = []
        
        async with aiohttp.ClientSession() as session:
            for site_id, config in self.sites.items():
                if not config.get("enabled", True):
                    continue
                
                # Filter by region/category if specified
                if region and config.get("region") != region:
                    continue
                if category and category not in config.get("categories", []):
                    continue
                
                try:
                    site_events = await self._fetch_site(session, site_id, config)
                    events.extend(site_events)
                except Exception as e:
                    print(f"Warning: Error fetching from {site_id}: {e}")
        
        return events
    
    async def _fetch_site(self, session, site_id: str, config: dict) -> list[RawEvent]:
        """Fetch events from a single site."""
        url = config.get("url")
        if not url:
            return []
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                print(f"Warning: Got status {response.status} from {url}")
                return []
            html = await response.text()
        
        # Use site-specific parser
        parser = config.get("parser", "generic")
        if parser == "yoga_barn":
            return self._parse_yoga_barn(html, config)
        elif parser == "paradiso":
            return self._parse_paradiso(html, config)
        else:
            return []
    
    def _parse_yoga_barn(self, html: str, config: dict) -> list[RawEvent]:
        """Parse Yoga Barn website for events."""
        events = []
        now = datetime.now()
        
        # Yoga Barn has fixed schedule:
        # Friday nights - Ecstatic Dance (18+)
        # Sunday mornings - Ecstatic Dance (family friendly)
        
        # Find next Friday
        days_until_friday = (4 - now.weekday()) % 7
        if days_until_friday == 0 and now.hour >= 20:
            days_until_friday = 7
        next_friday = now + timedelta(days=days_until_friday)
        
        events.append(RawEvent(
            source_type=self.source_type,
            source_name="The Yoga Barn",
            source_id="yoga-barn-friday",
            text="Ecstatic Dance at The Yoga Barn. Friday nights, adults 18+. DJs guide you on a journey through music. Upstairs 170K, Downstairs 100K. Book on Megatix, arrive 1 hour early.",
            timestamp=now,
            message_id=f"yoga-barn-friday-{next_friday.strftime('%Y%m%d')}",
            region=config.get("region", "ubud"),
            categories=config.get("categories", ["dance"]),
            event_name="Ecstatic Dance",
            event_date=next_friday.strftime("%B %d"),
            event_time="6:30pm",
            location="The Yoga Barn",
            ticket_link="https://megatix.co.id/events/yoga-barn-ecstatic-dance",
        ))
        
        # Find next Sunday
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and now.hour >= 12:
            days_until_sunday = 7
        next_sunday = now + timedelta(days=days_until_sunday)
        
        events.append(RawEvent(
            source_type=self.source_type,
            source_name="The Yoga Barn",
            source_id="yoga-barn-sunday",
            text="Ecstatic Dance at The Yoga Barn. Sunday mornings, family friendly (kids 12+ welcome). Followed by Sunday Sessions live music and community buffet at Garden Kafe.",
            timestamp=now,
            message_id=f"yoga-barn-sunday-{next_sunday.strftime('%Y%m%d')}",
            region=config.get("region", "ubud"),
            categories=config.get("categories", ["dance"]),
            event_name="Ecstatic Dance + Sunday Sessions",
            event_date=next_sunday.strftime("%B %d"),
            event_time="10am",
            location="The Yoga Barn",
            ticket_link="https://megatix.co.id/events/yoga-barn-ecstatic-dance",
        ))
        
        return events
    
    def _parse_paradiso(self, html: str, config: dict) -> list[RawEvent]:
        """Parse Paradiso website for events."""
        # TODO: Implement Paradiso parser
        return []
