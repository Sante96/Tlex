"""Benchmark: find optimal clients-per-worker for Telegram streaming.

Creates 1..N Pyrogram clients from each worker's session_string and
downloads the same file chunk in parallel to measure throughput scaling.

NOTE: file_reference is session-specific, so each client needs its own
fresh file_id obtained by re-fetching the original Telegram message.

Usage:
    uv run python scripts/benchmark_workers.py
    uv run python scripts/benchmark_workers.py --max-clients 8 --test-mb 10
"""

import asyncio
import sys
import time

from pyrogram import Client

# Add project root to path
sys.path.insert(0, ".")

from app.config import get_settings
from app.database import async_session_maker, engine
from app.models.media import MediaPart
from app.models.worker import Worker, WorkerStatus

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()

PYROGRAM_CHUNK_SIZE = 1024 * 1024  # 1 MB


async def get_test_part(session: AsyncSession) -> MediaPart | None:
    """Get the largest media part from DB (need channel_id + message_id for refresh)."""
    query = select(MediaPart).order_by(MediaPart.file_size.desc()).limit(1)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def refresh_file_id(client: Client, part: MediaPart) -> str:
    """Refresh file_id by fetching the original message (per-client, per-session)."""
    messages = await client.get_messages(
        chat_id=part.channel_id,
        message_ids=part.message_id,
    )
    message = messages if not isinstance(messages, list) else messages[0]
    doc = message.document or message.video
    if not doc:
        raise RuntimeError(f"No document in message {part.message_id}")
    return doc.file_id


async def create_clients_from_worker(worker: Worker, count: int) -> list[Client]:
    """Create N Pyrogram clients from a worker's session strings."""
    clients: list[Client] = []

    # Primary client
    primary = Client(
        name=f"bench_{worker.id}_0",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        session_string=worker.session_string,
        in_memory=True,
    )
    await primary.start()
    clients.append(primary)

    if count <= 1:
        return clients

    # Extra clients from saved sessions or cloned from primary
    extra_sessions = worker.extra_sessions or []
    for i in range(count - 1):
        session_str = extra_sessions[i] if i < len(extra_sessions) else worker.session_string
        try:
            c = Client(
                name=f"bench_{worker.id}_{i+1}",
                api_id=settings.api_id,
                api_hash=settings.api_hash,
                session_string=session_str,
                in_memory=True,
            )
            await c.start()
            clients.append(c)
        except Exception as e:
            print(f"  [!] Failed to create client {i+1}: {e}")
            break

    return clients


async def download_chunk(client: Client, file_id: str, offset: int, limit: int) -> int:
    """Download chunks with one client, return bytes read."""
    total = 0
    async for chunk in client.stream_media(file_id, offset=offset, limit=limit):
        total += len(chunk)
    return total


async def parallel_download(
    clients: list[Client],
    file_ids: dict[int, str],
    total_chunks: int,
) -> tuple[int, float]:
    """Download total_chunks split across clients. Returns (bytes, seconds)."""
    n = len(clients)
    per_client = total_chunks // n
    remainder = total_chunks % n

    tasks = []
    offset = 0
    for i, client in enumerate(clients):
        limit = per_client + (1 if i < remainder else 0)
        if limit == 0:
            continue
        fid = file_ids[id(client)]
        tasks.append(download_chunk(client, fid, offset, limit))
        offset += limit

    start = time.perf_counter()
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    return sum(results), elapsed


async def run_benchmark(max_clients: int = 8, test_mb: int = 10):
    test_chunks = test_mb  # 1 chunk = 1 MB

    print("=" * 60)
    print("TLEX Worker Bandwidth Benchmark")
    print("=" * 60)

    async with async_session_maker() as session:
        # Get test part (with channel_id + message_id for refresh)
        part = await get_test_part(session)
        if not part:
            print("[!] No media files in DB. Scan some media first.")
            return
        print(f"Test file: {part.file_size / (1024**3):.2f} GB (part {part.id})")
        print(f"Test size: {test_mb} MB per run")
        print(f"Channel: {part.channel_id} | Message: {part.message_id}")
        print()

        # Get workers
        workers_result = await session.execute(
            select(Worker).where(Worker.status != WorkerStatus.OFFLINE)
        )
        workers = workers_result.scalars().all()

        if not workers:
            print("[!] No active workers found.")
            return

        for worker in workers:
            print(f"--- Worker {worker.id} | {worker.phone_number} | "
                  f"{'Premium' if worker.is_premium else 'Standard'} ---")

            # Create up to max_clients
            actual_max = min(max_clients, 10)
            print(f"Creating up to {actual_max} clients...")
            clients = await create_clients_from_worker(worker, actual_max)
            actual_max = len(clients)
            print(f"  Created {actual_max} clients")

            # Refresh file_id for each client (file_reference is session-specific)
            print("  Refreshing file_ids...", end="", flush=True)
            file_ids: dict[int, str] = {}
            try:
                for c in clients:
                    fid = await refresh_file_id(c, part)
                    file_ids[id(c)] = fid
                print(f" OK ({len(file_ids)} refreshed)")
            except Exception as e:
                print(f" FAILED: {e}")
                for c in clients:
                    try:
                        await c.stop()
                    except Exception:
                        pass
                continue

            # Warmup (download 1 chunk to ensure connection is hot)
            print("  Warmup...", end="", flush=True)
            try:
                await download_chunk(clients[0], file_ids[id(clients[0])], 0, 1)
                print(" OK")
            except Exception as e:
                print(f" FAILED: {e}")
                for c in clients:
                    try:
                        await c.stop()
                    except Exception:
                        pass
                continue

            # Test 1..N clients
            results = []
            print()
            print(f"  {'Clients':>8} | {'Speed':>10} | {'Time':>8} | {'Improvement':>12}")
            print(f"  {'-'*8} | {'-'*10} | {'-'*8} | {'-'*12}")

            for n in range(1, actual_max + 1):
                subset = clients[:n]

                # 3 iterations, take best
                best_speed = 0.0
                best_elapsed = 999.0

                for _ in range(3):
                    try:
                        total_bytes, elapsed = await parallel_download(
                            subset, file_ids, test_chunks,
                        )
                    except Exception as e:
                        print(f"\n  [!] Download error with {n} clients: {e}")
                        total_bytes, elapsed = 0, 999.0

                    if elapsed > 0 and total_bytes > 0:
                        speed = (total_bytes / (1024 * 1024)) / elapsed
                    else:
                        speed = 0
                    if speed > best_speed:
                        best_speed = speed
                        best_elapsed = elapsed

                improvement = ""
                if results:
                    prev = results[-1]["speed"]
                    if prev > 0:
                        pct = ((best_speed - prev) / prev) * 100
                        improvement = f"+{pct:.1f}%" if pct > 0 else f"{pct:.1f}%"

                results.append({"clients": n, "speed": best_speed, "elapsed": best_elapsed})

                print(f"  {n:>8} | {best_speed:>8.1f} MB/s | {best_elapsed:>6.2f}s | {improvement:>12}")

            # Find optimal (last with >15% improvement)
            optimal = 1
            for i in range(1, len(results)):
                prev = results[i - 1]["speed"]
                curr = results[i]["speed"]
                if prev > 0 and ((curr - prev) / prev) > 0.15:
                    optimal = results[i]["clients"]

            peak_speed = max(r["speed"] for r in results)
            peak_clients = next(r["clients"] for r in results if r["speed"] == peak_speed)

            print()
            print(f"  Peak:    {peak_speed:.1f} MB/s @ {peak_clients} clients")
            print(f"  Optimal: {optimal} clients (>15% improvement threshold)")
            print()

            # Cleanup
            for c in clients:
                try:
                    await c.stop()
                except Exception:
                    pass

    await engine.dispose()
    print("=" * 60)
    print("Done. Update CLIENTS_PER_WORKER_PREMIUM / CLIENTS_PER_WORKER_STANDARD")
    print("in app/core/worker_manager.py with the optimal values above.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark Telegram worker bandwidth")
    parser.add_argument("--max-clients", type=int, default=8, help="Max clients to test per worker (default: 8)")
    parser.add_argument("--test-mb", type=int, default=10, help="MB to download per test (default: 10)")
    args = parser.parse_args()

    asyncio.run(run_benchmark(max_clients=args.max_clients, test_mb=args.test_mb))
