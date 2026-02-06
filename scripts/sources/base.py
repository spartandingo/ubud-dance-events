"""
Base class for event sources.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib
import re


@dataclass
class RawEvent:
    """Raw event data from any source."""
    source_type: str  # 'whatsapp', 'telegram', 'facebook', etc.
    source_name: str  # Group/channel name
    source_id: str    # Group JID, channel ID, etc.
    text: str
    timestamp: datetime
    message_id: str = ""
    author: str = ""
    
    # Region and category tags (from config)
    region: str = ""
    categories: list[str] = field(default_factory=list)
    
    # Parsed fields (filled by parser)
    event_name: str = ""
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    location: Optional[str] = None
    ticket_link: Optional[str] = None
    
    # Deduplication
    signature: str = field(default="", repr=False)
    
    def __post_init__(self):
        if not self.signature:
            self.signature = self._compute_signature()
    
    def _compute_signature(self) -> str:
        """Create signature for deduplication based on normalized content."""
        # Normalize: lowercase, collapse whitespace, strip
        normalized = re.sub(r'\s+', ' ', self.text.lower().strip())
        # Use first 300 chars — enough to identify unique events
        return hashlib.md5(normalized[:300].encode()).hexdigest()


@dataclass
class GroupConfig:
    """Configuration for a single group/channel."""
    jid: str           # Group JID or channel ID
    name: str          # Display name
    region: str        # Region ID (e.g., 'ubud', 'bali', 'northern-rivers')
    categories: list[str]  # Category IDs (e.g., ['dance', 'tantra'])
    
    @classmethod
    def from_dict(cls, jid: str, data: dict) -> "GroupConfig":
        """Create from config dict (handles both old and new formats)."""
        if isinstance(data, str):
            # Old format: JID -> name string
            return cls(jid=jid, name=data, region="", categories=[])
        else:
            # New format: JID -> {name, region, categories}
            return cls(
                jid=jid,
                name=data.get("name", jid),
                region=data.get("region", ""),
                categories=data.get("categories", [])
            )


class EventSource(ABC):
    """Abstract base class for event sources."""
    
    source_type: str = "unknown"
    
    @abstractmethod
    async def fetch_events(
        self,
        days: int = 7,
        search_terms: list[str] = None,
        region: str = None,
        category: str = None
    ) -> list[RawEvent]:
        """Fetch raw events from this source.
        
        Args:
            days: Number of days to look back
            search_terms: Terms to filter event content
            region: Filter by region ID (None = all regions)
            category: Filter by category ID (None = all categories)
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this source is configured and available."""
        pass
