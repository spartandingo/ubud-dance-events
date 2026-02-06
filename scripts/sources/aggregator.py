"""
Event aggregator - combines multiple sources with deduplication.
"""
import asyncio
from typing import Optional
from .base import EventSource, RawEvent
from .parser import parse_event


class EventAggregator:
    """Aggregates events from multiple sources with deduplication."""
    
    def __init__(self, sources: list[EventSource] = None):
        self.sources = sources or []
    
    def add_source(self, source: EventSource):
        """Add an event source."""
        self.sources.append(source)
    
    async def fetch_all(
        self,
        days: int = 7,
        search_terms: list[str] = None,
        region: str = None,
        category: str = None
    ) -> list[RawEvent]:
        """
        Fetch events from all sources and deduplicate.
        
        Args:
            days: Number of days to look back
            search_terms: Terms to filter events by
            region: Filter by region ID (None = all regions)
            category: Filter by category ID (None = all categories)
        
        Returns:
            List of unique, parsed events
        """
        all_events: list[RawEvent] = []
        
        # Fetch from all available sources concurrently
        tasks = []
        available_sources = []
        
        for source in self.sources:
            if source.is_available():
                tasks.append(source.fetch_events(
                    days=days,
                    search_terms=search_terms,
                    region=region,
                    category=category
                ))
                available_sources.append(source)
            else:
                print(f"Skipping {source.source_type}: not available")
        
        if not tasks:
            print("No sources available!")
            return []
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for source, result in zip(available_sources, results):
            if isinstance(result, Exception):
                print(f"Error fetching from {source.source_type}: {result}")
                continue
            all_events.extend(result)
        
        # Deduplicate by signature
        seen_signatures: set[str] = set()
        unique_events: list[RawEvent] = []
        
        for event in all_events:
            if event.signature not in seen_signatures:
                seen_signatures.add(event.signature)
                # Parse and enrich
                parse_event(event)
                unique_events.append(event)
        
        # Sort by event date (if available), then by post timestamp
        def sort_key(e: RawEvent):
            # Prefer parsed event_date, fall back to timestamp
            return (e.event_date or "", e.timestamp.isoformat())
        
        unique_events.sort(key=sort_key)
        
        return unique_events
    
    def get_source_stats(self) -> dict:
        """Get availability stats for all sources."""
        return {
            source.source_type: {
                "available": source.is_available(),
            }
            for source in self.sources
        }
