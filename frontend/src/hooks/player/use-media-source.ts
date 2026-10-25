"use client";

import { useEffect } from "react";

// Download at most this far past the playhead: the rest of the browser's quota (~150 MB
// of video in desktop Chrome) keeps played video for backward seeks. Past the quota the
// browser evicts the oldest data.
const AHEAD_SECONDS = 60;
// The init segment (ftyp + moov) comes before the first fragment
const MAX_INIT_BYTES = 4 * 1024 * 1024;

// ponytail: generic codec strings. Chromium only matches the codec family against the
// init segment, not the profile; parse avcC/hvcC if another browser needs exact ones.
const VIDEO_CODECS: Record<string, string> = {
  avc1: "avc1.640028",
  avc3: "avc3.640028",
  hvc1: "hvc1.1.6.L93.B0",
  hev1: "hev1.1.6.L93.B0",
};

// iPhone Safari (iOS 17.1+) has only ManagedMediaSource: MSE where the browser decides
// when to buffer and may evict, which seekLocally already handles through `buffered`
function mediaSourceClass(): typeof MediaSource | undefined {
  return (
    window.MediaSource ??
    (window as { ManagedMediaSource?: typeof MediaSource }).ManagedMediaSource
  );
}

function mimeFor(init: Uint8Array): string | null {
  const text = new TextDecoder("latin1").decode(init);
  const entries = text.slice(text.indexOf("stsd"));
  const box = Object.keys(VIDEO_CODECS).find((b) => entries.includes(b));
  if (!box) return null;
  const codecs = [VIDEO_CODECS[box], ...(entries.includes("mp4a") ? ["mp4a.40.2"] : [])];
  const type = `video/mp4; codecs="${codecs.join(", ")}"`;
  return mediaSourceClass()?.isTypeSupported(type) ? type : null;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function appended(sb: SourceBuffer) {
  return new Promise<void>((resolve, reject) => {
    const done = (e: Event) => {
      sb.removeEventListener("updateend", done);
      sb.removeEventListener("error", done);
      if (e.type === "error") reject(new Error("append failed"));
      else resolve();
    };
    sb.addEventListener("updateend", done);
    sb.addEventListener("error", done);
  });
}

/** Feed the fragmented MP4 of `url` into `ms`. False: MSE can't play it. */
async function feed(video: HTMLVideoElement, ms: MediaSource, url: string, signal: AbortSignal) {
  const response = await fetch(url, { signal });
  if (!response.ok || !response.body) throw new Error(`stream ${response.status}`);
  const reader = response.body.getReader();
  const ahead = () => video.buffered.end(video.buffered.length - 1) - video.currentTime;
  let sb: SourceBuffer | null = null;
  let head = new Uint8Array(0);

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    let chunk = value;
    if (!sb) {
      const joined = new Uint8Array(head.length + value.length);
      joined.set(head);
      joined.set(value, head.length);
      head = joined;
      if (!new TextDecoder("latin1").decode(head).includes("moof")) {
        if (head.length > MAX_INIT_BYTES) return false;
        continue;
      }
      const type = mimeFor(head);
      if (!type) return false;
      sb = ms.addSourceBuffer(type);
      chunk = head;
    }

    for (;;) {
      try {
        sb.appendBuffer(chunk);
        break;
      } catch (e) {
        if ((e as DOMException).name !== "QuotaExceededError") throw e;
        await sleep(1000); // full: playback makes room, the browser evicts played data
        if (signal.aborted) return true;
      }
    }
    await appended(sb);

    while (video.buffered.length && ahead() > AHEAD_SECONDS) {
      await sleep(1000);
      if (signal.aborted) return true;
    }
  }
  if (ms.readyState === "open") ms.endOfStream();
  return true;
}

/**
 * Play `url` through Media Source Extensions: a progressive response is a "streaming"
 * resource to the browser, which then refuses every seek (seekable is [0, 0]) even
 * into the buffered part. Falls back to a plain src where MSE can't play the stream.
 */
export function useMediaSource(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  url: string | undefined,
) {
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !url) return;
    const MS = mediaSourceClass();
    if (!MS) {
      video.src = url; // iPhones before iOS 17.1
      return;
    }
    // ManagedMediaSource opens only with AirPlay off (or an HLS source for AirPlay)
    if (MS !== window.MediaSource) video.disableRemotePlayback = true;
    const controller = new AbortController();
    const ms = new MS();
    const objectUrl = URL.createObjectURL(ms);
    video.src = objectUrl;
    ms.addEventListener(
      "sourceopen",
      () => {
        feed(video, ms, url, controller.signal)
          .then((ok) => {
            if (!ok && !controller.signal.aborted) {
              controller.abort();
              video.src = url;
            }
          })
          .catch(() => {
            if (!controller.signal.aborted && ms.readyState === "open") {
              ms.endOfStream("network");
            }
          });
      },
      { once: true },
    );
    return () => {
      controller.abort();
      URL.revokeObjectURL(objectUrl);
    };
  }, [videoRef, url]);
}
