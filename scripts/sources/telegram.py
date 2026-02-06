"""
Telegram event source using Telethon.
"""
import asyncio
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .base import EventSource, RawEvent, GroupConfig

try:
    from telethon import TelegramClient
    from telethon.tl.types import Channel, Chat
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False


class TelegramSource(EventSource):
    """Fetch events from Telegram groups/channels via Telethon."""
    
    source_type = "telegram"
    
    def __init__(
        self,
        groups_config: dict,
        api_id: Optional[str] = None,
        api_hash: Optional[str] = None,
        session_path: Optional[str] = None
    ):
        """
        Args:
            groups_config: Dict mapping group/channel ID -> config dict
            api_id: Telegram API ID (from my.telegram.org)
            api_hash: Telegram API hash
            session_path: Path to store session file
        """
        self.groups = [
            GroupConfig.from_dict(gid, data)
            for gid, data in groups_config.items()
        ]
        self.api_id = api_id or os.getenv("TELEGRAM_API_ID")
        self.api_hash = api_hash or os.getenv("TELEGRAM_API_HASH")
        
        # Default session path in skill directory
        if session_path:
            self.session_path = session_path
        else:
            skill_dir = Path(__file__).parent.parent.parent
            self.session_path = str(skill_dir / ".telegram_session")
        
        self._client: Optional[TelegramClient] = None
    
    def is_available(self) -> bool:
        """Check if Telethon is installed and credentials are configured."""
        if not TELETHON_AVAILABLE:
            return False
        if not self.api_id or not self.api_hash:
            return False
        return True
    
    def _filter_groups(self, region: str = None, category: str = None) -> list[GroupConfig]:
        """Filter groups by region and/or category."""
        filtered = self.groups
        
        if region:
            filtered = [g for g in filtered if g.region == region]
        
        if category:
            filtered = [g for g in filtered if category in g.categories]
        
        return filtered
    
    async def _get_client(self) -> TelegramClient:
        """Get or create Telegram client."""
        if self._client is None:
            self._client = TelegramClient(
                self.session_path,
                int(self.api_id),
                self.api_hash
            )
        if not self._client.is_connected():
            await self._client.connect()
            if not await self._client.is_user_authorized():
                raise RuntimeError(
                    "Telegram not authorized. Run 'python -m scripts.telegram_auth' to authenticate."
                )
        return self._client
    
    async def fetch_events(
        self,
        days: int = 7,
        search_terms: list[str] = None,
        region: str = None,
        category: str = None
    ) -> list[RawEvent]:
        """Fetch events from configured Telegram groups."""
        if not self.is_available():
            return []
        
        if search_terms is None:
            search_terms = ["dance", "ecstatic", "improv", "movement", "Paradiso", "RESONANZ", "workshop", "jam"]
        
        # Compile search pattern
        pattern = re.compile('|'.join(re.escape(t) for t in search_terms), re.IGNORECASE)
        
        after_date = datetime.now() - timedelta(days=days)
        events = []
        
        # Filter groups by region/category
        groups_to_fetch = self._filter_groups(region, category)
        
        try:
            client = await self._get_client()
            
            for group in groups_to_fetch:
                try:
                    # Handle both string IDs and int IDs
                    group_ref = group.jid
                    if isinstance(group_ref, str) and group_ref.lstrip('-').isdigit():
                        entity = await client.get_entity(int(group_ref))
                    else:
                        entity = await client.get_entity(group_ref)
                    
                    # Check if this is a forum (has topics/sub-channels)
                    is_forum = hasattr(entity, 'forum') and entity.forum
                    
                    if is_forum:
                        # Fetch from all topics in the forum
                        events.extend(await self._fetch_forum_messages(
                            client, entity, group, pattern, after_date
                        ))
                    else:
                        # Regular group - fetch normally
                        events.extend(await self._fetch_group_messages(
                            client, entity, group, pattern, after_date
                        ))
                        
                except Exception as e:
                    print(f"Warning: Could not fetch from {group.name}: {e}")
                    continue
        
        finally:
            if self._client:
                await self._client.disconnect()
                self._client = None
        
        return events
    
    async def disconnect(self):
        """Disconnect the client."""
        if self._client and self._client.is_connected():
            await self._client.disconnect()
            self._client = None
    
    async def _fetch_group_messages(
        self, client, entity, group: GroupConfig, pattern, after_date
    ) -> list[RawEvent]:
        """Fetch messages from a regular group."""
        events = []
        
        async for message in client.iter_messages(entity, limit=200):
            if message.date.replace(tzinfo=None) < after_date:
                break
            
            text = message.text or ""
            if len(text) < 50:
                continue
            
            # Filter by search terms
            if not pattern.search(text):
                continue
            
            events.append(RawEvent(
                source_type=self.source_type,
                source_name=group.name,
                source_id=group.jid,
                text=text,
                timestamp=message.date.replace(tzinfo=None),
                message_id=str(message.id),
                author=str(message.sender_id) if message.sender_id else "",
                region=group.region,
                categories=group.categories,
            ))
        
        return events
    
    async def _fetch_forum_messages(
        self, client, entity, group: GroupConfig, pattern, after_date
    ) -> list[RawEvent]:
        """Fetch messages from all topics in a forum group."""
        events = []
        
        try:
            # For forums, we can still iterate messages - they include reply_to_msg_id
            # which tells us which topic they belong to. We'll just fetch all messages
            # and track topic names as we go.
            topic_names = {}
            
            async for message in client.iter_messages(entity, limit=500):
                if message.date.replace(tzinfo=None) < after_date:
                    break
                
                text = message.text or ""
                if len(text) < 50:
                    continue
                
                # Filter by search terms
                if not pattern.search(text):
                    continue
                
                # Try to identify topic from reply_to
                topic_id = None
                if hasattr(message, 'reply_to') and message.reply_to:
                    if hasattr(message.reply_to, 'forum_topic'):
                        topic_id = message.reply_to.reply_to_top_id or message.reply_to.reply_to_msg_id
                
                # Use topic ID in source name if available
                source_name = group.name
                source_id = group.jid
                if topic_id:
                    source_name = f"{group.name} (topic {topic_id})"
                    source_id = f"{group.jid}:{topic_id}"
                
                events.append(RawEvent(
                    source_type=self.source_type,
                    source_name=source_name,
                    source_id=source_id,
                    text=text,
                    timestamp=message.date.replace(tzinfo=None),
                    message_id=str(message.id),
                    author=str(message.sender_id) if message.sender_id else "",
                    region=group.region,
                    categories=group.categories,
                ))
                    
        except Exception as e:
            print(f"  Warning: Error fetching from forum {group.name}: {e}")
            # Fall back to regular fetch
            events = await self._fetch_group_messages(
                client, entity, group, pattern, after_date
            )
        
        return events
