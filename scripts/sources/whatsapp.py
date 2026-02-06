"""
WhatsApp event source using wacli.
"""
import subprocess
import json
import asyncio
from datetime import datetime, timedelta
from .base import EventSource, RawEvent, GroupConfig


class WhatsAppSource(EventSource):
    """Fetch events from WhatsApp groups via wacli."""
    
    source_type = "whatsapp"
    
    def __init__(self, groups_config: dict):
        """
        Args:
            groups_config: Dict mapping group JID -> config (name, region, categories)
                          Supports both old format (JID -> name) and new format (JID -> dict)
        """
        self.groups = [
            GroupConfig.from_dict(jid, data)
            for jid, data in groups_config.items()
        ]
    
    def is_available(self) -> bool:
        """Check if wacli is available and authenticated."""
        try:
            result = subprocess.run(
                ["wacli", "doctor", "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                # Need to be authenticated (connected not required for local search)
                return data.get("success") and data.get("data", {}).get("authenticated", False)
            return False
        except Exception:
            return False
    
    def _filter_groups(self, region: str = None, category: str = None) -> list[GroupConfig]:
        """Filter groups by region and/or category."""
        filtered = self.groups
        
        if region:
            filtered = [g for g in filtered if g.region == region]
        
        if category:
            filtered = [g for g in filtered if category in g.categories]
        
        return filtered
    
    async def fetch_events(
        self,
        days: int = 7,
        search_terms: list[str] = None,
        region: str = None,
        category: str = None
    ) -> list[RawEvent]:
        """Fetch events from configured WhatsApp groups."""
        after_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        events = []
        seen_ids = set()
        
        # Filter groups by region/category
        groups_to_fetch = self._filter_groups(region, category)
        
        for group in groups_to_fetch:
            # Get all messages first
            messages = await self._list_messages(group.jid, after_date, limit=200)
            
            for msg in messages:
                msg_id = msg.get("ID", "") or msg.get("MsgID", "")
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)
                
                # Try Text first, fall back to DisplayText
                text = msg.get("Text", "") or msg.get("DisplayText", "")
                if not text or len(text) < 50:
                    continue
                
                # If search_terms provided AND not filtering by category, apply text filter
                # (When filtering by category, we trust the group assignment)
                if search_terms and not category:
                    text_lower = text.lower()
                    if not any(term.lower() in text_lower for term in search_terms):
                        continue
                
                # Parse timestamp
                ts_str = msg.get("Timestamp", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except:
                    ts = datetime.now()
                
                events.append(RawEvent(
                    source_type=self.source_type,
                    source_name=group.name,
                    source_id=group.jid,
                    text=text,
                    timestamp=ts,
                    message_id=msg_id,
                    region=group.region,
                    categories=group.categories,
                ))
        
        return events
    
    async def _list_messages(self, group_jid: str, after_date: str, limit: int = 100) -> list[dict]:
        """List messages from a group after a date."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "wacli", "messages", "list",
                "--chat", group_jid,
                "--after", after_date,
                "--limit", str(limit),
                "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            data = json.loads(stdout.decode())
            if data.get("success") and data.get("data", {}).get("messages"):
                return data["data"]["messages"]
        except Exception as e:
            print(f"Warning: Error listing messages from {group_jid}: {e}")
        return []
    
    async def _search_group(self, group_jid: str, after_date: str, term: str) -> list[dict]:
        """Search a group for messages matching a term."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "wacli", "messages", "search", term,
                "--chat", group_jid,
                "--after", after_date,
                "--limit", "30",
                "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            data = json.loads(stdout.decode())
            if data.get("success") and data.get("data", {}).get("messages"):
                return data["data"]["messages"]
        except Exception:
            pass
        return []
