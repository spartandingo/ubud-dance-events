#!/usr/bin/env python3
"""Find specific Telegram groups/channels by name."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

async def main():
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_path = Path(__file__).parent.parent / ".telegram_session"
    
    client = TelegramClient(str(session_path), int(api_id), api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        print("Not authorized - run telegram_auth.py first")
        return
    
    search_terms = sys.argv[1:] if len(sys.argv) > 1 else ["CONTACT", "CI", "Polina"]
    
    print("Searching dialogs for groups matching:", search_terms)
    print("-" * 60)
    
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        name = dialog.name or ""
        
        # Only groups and channels
        if not isinstance(entity, (Channel, Chat)):
            continue
        
        # Check if any search term matches
        name_lower = name.lower()
        if any(term.lower() in name_lower for term in search_terms):
            entity_id = entity.id
            if isinstance(entity, Channel):
                # Channels need the -100 prefix
                full_id = f"-100{entity_id}"
            else:
                full_id = f"-{entity_id}"
            
            username = getattr(entity, 'username', None)
            username_str = f" (@{username})" if username else ""
            
            print(f"Name: {name}{username_str}")
            print(f"  ID: {full_id}")
            print(f"  Type: {'Channel/Supergroup' if isinstance(entity, Channel) else 'Group'}")
            
            # Check for forum/topics
            if hasattr(entity, 'forum') and entity.forum:
                print(f"  Forum: Yes (has topics/sub-channels)")
            print()
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
