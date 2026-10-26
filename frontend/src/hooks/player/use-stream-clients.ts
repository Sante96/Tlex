"use client";

import { useEffect, useState } from "react";
import { getStreamClients } from "@/lib/api";

const POLL_MS = 2000;

export interface StreamClients {
  inUse: number;
  total: number;
  /** The buffer grew since the last look: data is arriving */
  downloading: boolean;
}

/** The player's client ring: polled every 2 s while the player is open */
export function useStreamClients(
  mediaId: number,
  videoRef: React.RefObject<HTMLVideoElement | null>,
): StreamClients | null {
  const [clients, setClients] = useState<StreamClients | null>(null);

  useEffect(() => {
    let cancelled = false;
    let lastBuffered = -1;

    const look = async () => {
      const counts = await getStreamClients(mediaId);
      const video = videoRef.current;
      const buffered =
        video && video.buffered.length ? video.buffered.end(video.buffered.length - 1) : 0;
      const downloading = lastBuffered >= 0 && buffered > lastBuffered;
      lastBuffered = buffered;
      if (!cancelled && counts) setClients({ ...counts, downloading });
    };

    look();
    const timer = setInterval(look, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [mediaId, videoRef]);

  return clients;
}
