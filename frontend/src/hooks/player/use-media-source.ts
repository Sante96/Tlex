"use client";

import { useEffect, useRef } from "react";
import { streamRead } from "@/lib/api/stream";

// Download at most this far past the playhead
const AHEAD_SECONDS = 60;
// Kept behind the playhead: short rewinds play from the buffer, longer ones ask the
// server again. Left to the browser, Safari evicts only what is 30 s behind: at a 4K
// concert's bitrate that alone is past its quota, and playback stopped at the buffer's end
const BEHIND_SECONDS = 10;
// Safari on iPhone and iPad (the only browsers with -webkit-touch-callout) evicts by
// itself past ~100 MB, and not only played video: an iPad cut out the playhead's own
// range and stalled 5 s into a seek (buffer [8, 34.7] [63.1, 93.5], a 14 Mbit/s film).
// There the buffer stays under that in bytes as well, at the title's bitrate
const IOS = typeof CSS !== "undefined" && CSS.supports("-webkit-touch-callout", "none");
const MAX_AHEAD_BYTES = 48e6;
const MAX_BEHIND_BYTES = 16e6;
// The init segment (ftyp + moov) comes before the first fragment
const MAX_INIT_BYTES = 4 * 1024 * 1024;
// A stream that ends this close to the title's end has ended (durations differ a little)
const END_MARGIN = 5;
// A stream can also stop with neither an error nor an end (an iPad waited forever at the
// buffer's end behind Cloudflare): playing with under LOW_SECONDS buffered, and nothing
// for STALL_SECONDS, it counts as broken and goes on in a new stream
const LOW_SECONDS = 30;
const STALL_SECONDS = 15;

// The video's codec string, read from its decoder configuration (avcC/hvcC) in the init
// segment: Chrome matches only the codec family, but Safari sets its decoder up from the
// string, and the generic "Main, level 3.1" of before made it fail on 4K Main 10 titles
// ("failed to decode" on an iPad, a crawl on an iPhone). `at`: the box's first byte after
// its type, in the latin1 text of the segment (one char per byte).
function videoCodec(init: Uint8Array, text: string): string | null {
  const entries = text.slice(text.indexOf("stsd"));
  const at = (box: string) => {
    const i = text.indexOf(box);
    return i < 0 ? -1 : i + 4;
  };
  const hex = (n: number) => n.toString(16).toUpperCase();
  let p = at("hvcC");
  if (p > 0) {
    // ISO/IEC 14496-15 annex E: hvc1.<space><profile>.<compatibility, bits reversed>.
    // <tier><level>.<constraint bytes, trailing zeros dropped>
    const sample = entries.includes("hev1") ? "hev1" : "hvc1";
    const b = init[p + 1];
    let compat = 0;
    for (let i = 0; i < 4; i++) compat = compat * 256 + init[p + 2 + i];
    let reversed = 0;
    for (let i = 0; i < 32; i++) reversed = reversed * 2 + (Math.floor(compat / 2 ** i) % 2);
    const constraints = Array.from(init.subarray(p + 6, p + 12));
    while (constraints.length && constraints[constraints.length - 1] === 0) constraints.pop();
    return [
      sample,
      ["", "A", "B", "C"][b >> 6] + (b & 0x1f),
      hex(reversed),
      (b & 0x20 ? "H" : "L") + init[p + 12],
      ...constraints.map(hex),
    ].join(".");
  }
  p = at("avcC");
  if (p > 0) {
    // avc1.<profile><compatibility><level>, two hex digits each
    const sample = entries.includes("avc3") ? "avc3" : "avc1";
    const bytes = [init[p + 1], init[p + 2], init[p + 3]];
    return `${sample}.${bytes.map((x) => x.toString(16).padStart(2, "0")).join("")}`;
  }
  return null;
}

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
  const video = videoCodec(init, text);
  if (!video) return null;
  const audio = text.slice(text.indexOf("stsd")).includes("mp4a");
  const codecs = [video, ...(audio ? ["mp4a.40.2"] : [])];
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

// ffmpeg starts a fragment at every keyframe (frag_keyframe): the moof box, then its mfhd
const MOOF = "moof\x00\x00\x00\x10mfhd";

/**
 * Remove what was played more than `keep` seconds ago. MSE removes on up to the next
 * keyframe (what follows can't be decoded without it), so the cut is at a keyframe
 * itself: with keyframes 10+ s apart (an anime's 10-bit encode) the playhead's own
 * frames went too, and playback stalled for good. False: nothing worth it.
 */
async function trimBehind(
  video: HTMLVideoElement,
  sb: SourceBuffer,
  keep: number,
  keyframes: number[],
) {
  if (!video.buffered.length) return false;
  const start = video.buffered.start(0);
  const end = keyframes.filter((k) => k <= video.currentTime - keep).pop();
  if (end === undefined || end - start < 1) return false;
  sb.remove(start, end);
  await appended(sb);
  return true;
}

/** Feed the fragmented MP4 of `url` into `ms`. False: MSE can't play it. */
async function feed(
  video: HTMLVideoElement,
  ms: MediaSource,
  url: string,
  duration: () => number,
  signal: AbortSignal,
  onHeaders: (headers: Headers) => void,
) {
  const response = await fetch(url, { signal });
  if (!response.ok || !response.body) throw new Error(`stream ${response.status}`);
  onHeaders(response.headers);
  // Where the stream starts in the title: its time 0 in the buffer
  const start = parseFloat(response.headers.get("X-Stream-Start-Time") ?? "");
  let reader = response.body.getReader();
  streamRead.bytes = 0; // a new stream: the backend counts it from zero too
  const ahead = () => video.buffered.end(video.buffered.length - 1) - video.currentTime;
  // The stream's bitrate so far (bytes per second of video), for the iOS byte limits
  const perSecond = () =>
    streamRead.bytes / Math.max(1, video.buffered.end(video.buffered.length - 1));
  const aheadLimit = () =>
    IOS ? Math.min(AHEAD_SECONDS, MAX_AHEAD_BYTES / perSecond()) : AHEAD_SECONDS;
  const behindLimit = () =>
    IOS ? Math.min(BEHIND_SECONDS, Math.max(1, MAX_BEHIND_BYTES / perSecond())) : BEHIND_SECONDS;
  let sb: SourceBuffer | null = null;
  let head = new Uint8Array(0);
  // Where the fragments start, in the buffer's time: where one begins, the buffer ends
  // at its keyframe. One split across two reads is missed, which only trims less
  const keyframes: number[] = [];
  // False: the stream was stopped while the buffer was full
  const append = async (buffer: SourceBuffer, piece: Uint8Array<ArrayBuffer>) => {
    for (;;) {
      try {
        buffer.appendBuffer(piece);
        break;
      } catch (e) {
        if ((e as DOMException).name !== "QuotaExceededError") throw e;
        // Full: what was played goes first, else playback makes room
        if (!(await trimBehind(video, buffer, 2, keyframes))) await sleep(1000);
        if (signal.aborted) return false;
      }
    }
    await appended(buffer);
    return true;
  };
  // A stream that broke or ended before the title's end goes on from the buffer's end, in
  // a new stream appended to the same buffer at its place: Cloudflare drops a response the
  // browser hasn't taken data from for 60 s (a pause past a minute), and a failed Telegram
  // read ends ffmpeg's output early. Null: nothing more to get, or no progress since the
  // last time.
  let resumedAt = -1;
  let resumed = false;
  const resume = async (buffer: SourceBuffer) => {
    if (signal.aborted || !video.buffered.length || !Number.isFinite(start)) return null;
    const at = start + video.buffered.end(video.buffered.length - 1);
    if (at <= resumedAt || at > duration() - END_MARGIN) return null;
    resumedAt = at;
    const next = new URL(url, location.href);
    next.searchParams.set("t", at.toFixed(3));
    const res = await fetch(next.pathname + next.search, { signal });
    const from = parseFloat(res.headers.get("X-Stream-Start-Time") ?? "");
    if (!res.ok || !res.body || !Number.isFinite(from)) return null;
    buffer.abort(); // a fragment cut short: the parser starts over at the new init segment
    buffer.timestampOffset = from - start;
    keyframes.push(from - start);
    resumed = true;
    streamRead.bytes = 0; // a new stream: the backend counts it from zero too
    return res.body.getReader();
  };
  // The next read, or "stalled" when playback is about to run dry and nothing comes
  const readOrStall = () => {
    let timer: ReturnType<typeof setInterval> | undefined;
    const stalled = new Promise<"stalled">((resolve) => {
      let quiet = 0;
      timer = setInterval(() => {
        const low = !video.paused && video.buffered.length > 0 && ahead() < LOW_SECONDS;
        quiet = low ? quiet + 1 : 0;
        if (quiet >= STALL_SECONDS) resolve("stalled");
      }, 1000);
    });
    return Promise.race([reader.read(), stalled]).finally(() => clearInterval(timer));
  };

  for (;;) {
    let read: Awaited<ReturnType<typeof readOrStall>>;
    try {
      read = await readOrStall();
    } catch (e) {
      const next = sb && (await resume(sb));
      if (!next) throw e;
      reader = next;
      continue;
    }
    if (read === "stalled") {
      reader.cancel().catch(() => {});
      // ponytail: temporary, with the player's [DIAG]: how often a stream hangs
      fetch("/api/v1/stream/diag", {
        method: "POST",
        body: JSON.stringify({ event: "stall", t: video.currentTime, buf: ahead() }),
        keepalive: true,
      }).catch(() => {});
      const next = sb && (await resume(sb));
      if (!next) throw new Error("stream stalled");
      reader = next;
      continue;
    }
    if (read.done) {
      const next = sb && (await resume(sb));
      if (!next) break;
      reader = next;
      continue;
    }
    const value = read.value;
    streamRead.bytes += value.byteLength;
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
      // ponytail: temporary, with the player's [DIAG]: the codec string it chose
      fetch("/api/v1/stream/diag", {
        method: "POST",
        body: JSON.stringify({ event: "codec", type, url }),
        keepalive: true,
      }).catch(() => {});
      if (!type) return false;
      sb = ms.addSourceBuffer(type);
      chunk = head;
    }

    const text = new TextDecoder("latin1").decode(chunk);
    let from = 0;
    for (let at = text.indexOf(MOOF); at >= 0; at = text.indexOf(MOOF, at + 1)) {
      const to = Math.max(from, at - 4); // the box starts with its size
      if (to > from && !(await append(sb, chunk.subarray(from, to)))) return true;
      // A resumed stream's first fragment: its keyframe went in with resume(), and the
      // buffer still ends where the broken stream left it
      if (resumed) resumed = false;
      else if (video.buffered.length) keyframes.push(video.buffered.end(video.buffered.length - 1));
      from = to;
    }
    if (!(await append(sb, chunk.subarray(from)))) return true;
    // Not on an empty buffer: on iOS behindLimit() reads its end
    if (video.buffered.length) await trimBehind(video, sb, behindLimit(), keyframes);

    while (video.buffered.length && ahead() > aheadLimit()) {
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
  /** The stream response's headers (where it starts) */
  onHeaders: (headers: Headers) => void,
  /** The title's, in seconds: a stream that ends before it goes on */
  duration: number,
) {
  const onHeadersRef = useRef(onHeaders);
  const durationRef = useRef(duration);
  useEffect(() => {
    onHeadersRef.current = onHeaders;
    durationRef.current = duration;
  }, [onHeaders, duration]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !url) return;
    const headers = (h: Headers) => onHeadersRef.current(h);
    const MS = mediaSourceClass();
    if (!MS) {
      // iPhones before iOS 17.1: the element fetches the stream itself, so ask for the
      // headers separately
      video.src = url;
      fetch(url, { method: "HEAD" }).then((r) => headers(r.headers), () => {});
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
        feed(video, ms, url, () => durationRef.current, controller.signal, headers)
          .then((ok) => {
            if (!ok && !controller.signal.aborted) {
              controller.abort();
              video.src = url;
            }
          })
          .catch((e) => {
            // ponytail: temporary, with the player's [DIAG]: why a stream ended
            fetch("/api/v1/stream/diag", {
              method: "POST",
              body: JSON.stringify({ event: "feed-error", error: String(e) }),
              keepalive: true,
            }).catch(() => {});
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
