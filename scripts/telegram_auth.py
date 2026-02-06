#!/usr/bin/env python3
"""
Telegram authentication helper.
Run this once to authenticate your Telegram account.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


async def main():
    try:
        from telethon import TelegramClient
    except ImportError:
        print("Telethon not installed. Run: pip install telethon")
        sys.exit(1)
    
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    
    if not api_id or not api_hash:
        print("Missing Telegram credentials!")
        print()
        print("1. Go to https://my.telegram.org")
        print("2. Log in and go to 'API development tools'")
        print("3. Create an app to get your api_id and api_hash")
        print("4. Create a .env file in the skill directory with:")
        print()
        print("   TELEGRAM_API_ID=your_api_id")
        print("   TELEGRAM_API_HASH=your_api_hash")
        print()
        sys.exit(1)
    
    session_path = Path(__file__).parent.parent / ".telegram_session"
    
    print("Connecting to Telegram...")
    client = TelegramClient(str(session_path), int(api_id), api_hash)
    
    await client.connect()
    
    if not await client.is_user_authorized():
        print()
        phone = input("Enter your phone number (with country code, e.g. +1234567890): ")
        await client.send_code_request(phone)
        code = input("Enter the code you received: ")
        
        try:
            await client.sign_in(phone, code)
        except Exception as e:
            if "Two-step verification" in str(e) or "password" in str(e).lower():
                password = input("Enter your 2FA password: ")
                await client.sign_in(password=password)
            else:
                raise
    
    me = await client.get_me()
    print()
    print(f"✅ Authenticated as: {me.first_name} (@{me.username})")
    print(f"   Session saved to: {session_path}")
    print()
    print("You can now run fetch-events.py with Telegram support!")
    
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
