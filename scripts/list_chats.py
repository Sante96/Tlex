"""List all chats/groups with their IDs."""

import asyncio

from pyrogram import Client
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session_maker
from app.models.worker import Worker


async def main():
    settings = get_settings()
    
    # Get session string from DB
    async with async_session_maker() as session:
        result = await session.execute(select(Worker).limit(1))
        worker = result.scalar_one_or_none()
        if not worker:
            print("No workers in database!")
            return
        session_string = worker.session_string
    
    # Create client directly
    client = Client(
        name="list_chats",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        session_string=session_string,
    )
    
    async with client:
        from pyrogram.raw import functions, types
        
        print("\n🔍 Finding Tlex group and its topics...\n")
        
        # First, find Tlex in dialogs to populate cache
        tlex_chat = None
        async for dialog in client.get_dialogs():
            if dialog.chat.title and "tlex" in dialog.chat.title.lower():
                tlex_chat = dialog.chat
                print(f"   ✅ Found: {tlex_chat.title} (ID: {tlex_chat.id})")
                break
        
        if not tlex_chat:
            print("   ❌ Tlex not found in dialogs")
            return
        
        # Now get forum topics using raw API
        try:
            peer = await client.resolve_peer(tlex_chat.id)
            
            result = await client.invoke(
                functions.channels.GetForumTopics(
                    channel=peer,
                    offset_date=0,
                    offset_id=0,
                    offset_topic=0,
                    limit=100,
                )
            )
            
            print(f"\n   📂 Found {len(result.topics)} topics:\n")
            for topic in result.topics:
                if hasattr(topic, 'title'):
                    print(f"      - {topic.title} (ID: {topic.id})")
                    
        except Exception as e:
            print(f"\n   ⚠️ Can't get topics (forum not enabled?): {e}")


if __name__ == "__main__":
    asyncio.run(main())
