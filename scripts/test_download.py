"""Test Telegram download directly."""

import asyncio
import sys

sys.path.insert(0, ".")

from app.config import get_settings
from app.database import async_session_maker
from app.core.worker_manager import worker_manager
from sqlalchemy import select
from app.models.media import MediaPart

settings = get_settings()


async def test_download():
    """Test downloading from Telegram."""
    async with async_session_maker() as session:
        # Load workers
        await worker_manager.load_workers(session)
        
        # Get a worker
        result = await worker_manager.get_best_worker(session)
        if not result:
            print("No workers available!")
            return
        
        worker, client = result
        print(f"Using worker: {worker.phone_number}")
        
        # Get first media part
        stmt = select(MediaPart).limit(1)
        result = await session.execute(stmt)
        part = result.scalar_one_or_none()
        
        if not part:
            print("No media parts found!")
            return
        
        print(f"Part: channel={part.channel_id}, message={part.message_id}")
        
        # Populate peer cache
        print("Populating peer cache...")
        async for dialog in client.get_dialogs():
            if dialog.chat and dialog.chat.id == part.channel_id:
                print(f"Found channel in cache")
                break
        
        # Get fresh file_id
        print("Getting fresh file_id...")
        messages = await client.get_messages(
            chat_id=part.channel_id,
            message_ids=part.message_id,
        )
        
        if not messages:
            print("Message not found!")
            return
        
        message = messages if not isinstance(messages, list) else messages[0]
        doc = message.document or message.video
        
        if not doc:
            print("No document in message!")
            return
        
        file_id = doc.file_id
        print(f"Fresh file_id: {file_id[:30]}...")
        
        # Try streaming from near end of file (like browser seeking for moov atom)
        file_size = doc.file_size
        print(f"File size: {file_size}")
        
        # Test offset near end
        test_offset = file_size - (1024 * 1024)  # 1MB from end
        aligned_offset = (test_offset // (1024 * 1024)) * (1024 * 1024)
        print(f"Testing offset {aligned_offset} (aligned from {test_offset})")
        
        chunk_count = 0
        total_bytes = 0
        
        try:
            async for chunk in client.stream_media(
                file_id,
                offset=aligned_offset,
                limit=1024 * 1024,
            ):
                chunk_count += 1
                total_bytes += len(chunk)
                print(f"Chunk {chunk_count}: {len(chunk)} bytes (total: {total_bytes})")
                
                if total_bytes >= 1024 * 1024:
                    break
            
            print(f"Done! Downloaded {total_bytes} bytes in {chunk_count} chunks")
        except Exception as e:
            print(f"Error with large offset: {e}")
        
        await worker_manager.shutdown()


if __name__ == "__main__":
    asyncio.run(test_download())
