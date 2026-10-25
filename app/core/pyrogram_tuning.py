"""Pyrogram tweaks for streaming throughput.

Profiled with py-spy on 2026-10-25, 4 streams at ~28 MB/s: the event loop thread was ~60%
busy and Pyrogram's one crypto thread ~40%, so a single process would top out around
45 MB/s. Apply before any client connects (app startup).
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import pyrogram
from pyrogram.connection import Connection
from pyrogram.connection.transport.tcp import TCP
from pyrogram.session import session as session_module

# Pyrogram's default mode 3 is TCP abridged *obfuscated*: AES-CTR over every byte on top of
# MTProto's own encryption, meant for getting past censorship. It was over half of the
# crypto thread's work, plus a thread hop per message.
PLAIN_TCP_ABRIDGED = 1
CRYPTO_THREADS = 4  # tgcrypto releases the GIL: 289 MB/s on 1 thread, ~1 GB/s on 4


async def _recv(self: TCP, length: int = 0) -> bytes | None:
    """TCP.recv joining the reads in a bytearray: the original's `bytes +=` copies all
    that was received so far on every read, ~8 MB copied per 1 MB chunk."""
    data = bytearray()
    while len(data) < length:
        try:
            chunk = await asyncio.wait_for(self.reader.read(length - len(data)), TCP.TIMEOUT)
        except OSError:  # TimeoutError included
            return None
        if not chunk:
            return None
        data += chunk
    return bytes(data)


def apply() -> None:
    session_module.Connection = partial(Connection, mode=PLAIN_TCP_ABRIDGED)
    TCP.recv = _recv
    pyrogram.crypto_executor = ThreadPoolExecutor(CRYPTO_THREADS, thread_name_prefix="CryptoWorker")
