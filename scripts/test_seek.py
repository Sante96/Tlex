"""Test Telegram seek capability for large files.

This script verifies if Pyrogram's stream_media offset parameter works correctly
for seeking to arbitrary positions in large files (>2GB).

Key findings to document:
- offset parameter is in CHUNKS (1MB each), NOT bytes
- limit parameter is also in chunks
- To seek to byte X, use offset = X // chunk_size
"""

import asyncio
import sys
import time

sys.path.insert(0, ".")

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.worker_manager import worker_manager
from app.database import async_session_maker
from app.models.media import MediaItem

settings = get_settings()

# Pyrogram's default chunk size
CHUNK_SIZE = 1024 * 1024  # 1MB


async def test_seek_capability():
    """Test if Telegram supports seeking in large files."""
    async with async_session_maker() as session:
        # Load workers
        count = await worker_manager.load_workers(session)
        print(f"Loaded {count} workers")

        if count == 0:
            print("No workers available!")
            return

        # Get a worker
        result = await worker_manager.get_best_worker(session)
        if not result:
            print("No workers available!")
            return

        worker, client = result
        print(f"Using worker: {worker.phone_number}")

        # Get first media item WITH all its parts
        stmt = select(MediaItem).options(selectinload(MediaItem.parts)).limit(1)
        result = await session.execute(stmt)
        media_item = result.scalar_one_or_none()

        if not media_item:
            print("No media items found!")
            return

        parts = sorted(media_item.parts, key=lambda p: p.part_index)
        total_size = sum(p.file_size for p in parts)

        print("\n=== Media Info ===")
        print(f"Title: {media_item.title}")
        print(f"Total parts: {len(parts)}")
        print(f"Total size: {total_size:,} bytes ({total_size / (1024**3):.2f} GB)")

        for i, part in enumerate(parts):
            print(f"  Part {i}: {part.file_size:,} bytes (msg {part.message_id})")
            print(f"           Range: {part.start_byte:,} - {part.end_byte:,}")

        # Use first part for single-part tests
        part = parts[0]
        print("\n=== Single Part Test (Part 0) ===")
        print(f"Channel: {part.channel_id}")
        print(f"Message: {part.message_id}")
        print(f"File size: {part.file_size:,} bytes ({part.file_size / (1024**3):.2f} GB)")

        # Populate peer cache
        print("\nPopulating peer cache...")
        async for dialog in client.get_dialogs():
            if dialog.chat and dialog.chat.id == part.channel_id:
                print("Found channel in cache")
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
        file_size = doc.file_size

        print("\n=== Test 1: Stream from START (offset=0) ===")
        await test_stream(client, file_id, offset_chunks=0, limit_chunks=2)

        print("\n=== Test 2: Stream from MIDDLE (offset=50% of file) ===")
        middle_chunk = (file_size // 2) // CHUNK_SIZE
        await test_stream(client, file_id, offset_chunks=middle_chunk, limit_chunks=2)

        print("\n=== Test 3: Stream from END (last 2MB) ===")
        end_chunk = max(0, (file_size // CHUNK_SIZE) - 2)
        await test_stream(client, file_id, offset_chunks=end_chunk, limit_chunks=2)

        print("\n=== Test 4: Seek performance comparison ===")
        # Test time to get first bytes from start vs middle
        await test_seek_performance(client, file_id, file_size)

        # Test multi-part seek if we have multiple parts
        if len(parts) > 1:
            print("\n=== Test 5: MULTI-PART SEEK (VirtualStreamReader) ===")
            await test_multipart_seek(session, media_item, parts, client)

        await worker_manager.shutdown()
        print("\n✅ Test completed!")


async def test_stream(client, file_id: str, offset_chunks: int, limit_chunks: int):
    """Test streaming from a specific offset."""
    print(f"  Offset: {offset_chunks} chunks ({offset_chunks * CHUNK_SIZE:,} bytes)")
    print(f"  Limit: {limit_chunks} chunks")

    start_time = time.time()
    chunk_count = 0
    total_bytes = 0
    first_chunk_time = None

    try:
        async for chunk in client.stream_media(
            file_id,
            offset=offset_chunks,
            limit=limit_chunks,
        ):
            if first_chunk_time is None:
                first_chunk_time = time.time() - start_time
            chunk_count += 1
            total_bytes += len(chunk)

            if chunk_count <= 3:
                print(f"  Chunk {chunk_count}: {len(chunk):,} bytes")

        elapsed = time.time() - start_time
        print(f"  ✓ Downloaded {total_bytes:,} bytes in {chunk_count} chunks")
        print(f"  ✓ First chunk: {first_chunk_time:.2f}s, Total: {elapsed:.2f}s")
        return True, first_chunk_time

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False, None


async def test_seek_performance(client, file_id: str, file_size: int):
    """Compare seek performance: start vs middle vs end."""
    positions = [
        ("Start (0%)", 0),
        ("Quarter (25%)", (file_size // 4) // CHUNK_SIZE),
        ("Middle (50%)", (file_size // 2) // CHUNK_SIZE),
        ("Three-quarters (75%)", (3 * file_size // 4) // CHUNK_SIZE),
        ("End (last 1MB)", max(0, (file_size // CHUNK_SIZE) - 1)),
    ]

    results = []
    for name, offset in positions:
        print(f"\n  Testing {name} (chunk {offset})...")
        start_time = time.time()

        try:
            async for chunk in client.stream_media(
                file_id,
                offset=offset,
                limit=1,  # Just 1 chunk
            ):
                elapsed = time.time() - start_time
                results.append((name, offset, elapsed, len(chunk)))
                print(f"    Got {len(chunk):,} bytes in {elapsed:.3f}s")
                break
        except Exception as e:
            print(f"    Error: {e}")
            results.append((name, offset, -1, 0))

    print("\n  === SEEK PERFORMANCE SUMMARY ===")
    print("  Position            | Offset Chunk | Time (s) | Bytes")
    print("  " + "-" * 60)
    for name, offset, elapsed, size in results:
        if elapsed >= 0:
            print(f"  {name:20} | {offset:12,} | {elapsed:8.3f} | {size:,}")
        else:
            print(f"  {name:20} | {offset:12,} | FAILED   |")

    # Analyze results
    times = [r[2] for r in results if r[2] >= 0]
    if len(times) >= 2:
        start_time = times[0]
        other_times = times[1:]
        avg_seek_time = sum(other_times) / len(other_times)

        print(f"\n  Start time: {start_time:.3f}s")
        print(f"  Avg seek time: {avg_seek_time:.3f}s")

        if avg_seek_time < start_time * 2:
            print("  ✅ SEEK WORKS! Server-side seeking appears functional.")
        else:
            print("  ⚠️ SEEK MAY BE SLOW - times increase with offset, possible full download.")


async def test_multipart_seek(session, media_item, parts, _client):
    """Test seeking across multiple parts using VirtualStreamReader."""
    from app.services.streaming import VirtualStreamReader

    total_size = sum(p.file_size for p in parts)

    print(f"  Total virtual size: {total_size:,} bytes")
    print(f"  Parts: {len(parts)}")

    # Test positions
    test_positions = []

    # Start of file (part 0)
    test_positions.append(("Start of Part 0", 0))

    # End of part 0 (just before boundary)
    part0_end = parts[0].file_size - CHUNK_SIZE
    test_positions.append(("End of Part 0", part0_end))

    # Start of part 1 (just after boundary)
    part1_start = parts[0].file_size + CHUNK_SIZE
    test_positions.append(("Start of Part 1", part1_start))

    # Boundary crossing (straddles part 0 and part 1)
    boundary = parts[0].file_size - (CHUNK_SIZE // 2)
    test_positions.append(("BOUNDARY CROSSING", boundary))

    # End of file (part 1)
    end_pos = total_size - CHUNK_SIZE
    test_positions.append(("End of Part 1", end_pos))

    print("\n  Testing VirtualStreamReader seek positions:")
    print("  " + "-" * 70)

    for name, byte_offset in test_positions:
        # Find which part this offset is in
        part_idx = "?"
        for i, p in enumerate(parts):
            if p.start_byte <= byte_offset < p.end_byte:
                part_idx = i
                break

        print(f"\n  {name} (byte {byte_offset:,}, part {part_idx}):")

        # Create fresh reader for each test (reader releases worker after read_range)
        reader = VirtualStreamReader(media_item, session)

        start_time = time.time()
        bytes_read = 0

        try:
            async for chunk in reader.read_range(byte_offset, byte_offset + CHUNK_SIZE):
                bytes_read += len(chunk)
                if bytes_read >= CHUNK_SIZE:
                    break

            elapsed = time.time() - start_time
            print(f"    ✓ Got {bytes_read:,} bytes in {elapsed:.3f}s")

        except Exception as e:
            print(f"    ✗ Error: {e}")

    print("\n  " + "-" * 70)
    print("  Multi-part seek test complete!")


if __name__ == "__main__":
    asyncio.run(test_seek_capability())
