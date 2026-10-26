"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { VolumeX } from "lucide-react";
import { motion } from "framer-motion";
import { DSButton } from "@/components/ds";
import { useRouter } from "next/navigation";
import { PlayerControls } from "./player-controls";
import {
  SubtitleRenderer,
  type SubtitleRendererHandle,
} from "./subtitle-renderer";
import {
  releaseStream,
  setCreditsStart,
  type Chapter,
  type MediaStream,
  type Profile,
} from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";
import { useAuth } from "@/contexts/auth-context";

import { usePlayerPreferences } from "@/hooks/player/use-player-preferences";
import { usePoolStatus } from "@/hooks/player/use-pool-status";
import { useStreamClients } from "@/hooks/player/use-stream-clients";
import { useVideoSync } from "@/hooks/player/use-video-sync";
import { useMediaSource } from "@/hooks/player/use-media-source";
import { useVideoEvents } from "@/hooks/player/use-video-events";
import { useVideoHotkeys } from "@/hooks/player/use-video-hotkeys";
import { useProgressSaving } from "@/hooks/player/use-progress-saving";
import { PoolWarningOverlay } from "./pool-warning";
import { EpisodePicker } from "./episode-picker";
import { NextEpisodeOverlay, UpNextBackdrop } from "./next-episode-overlay";
import { useNextEpisode } from "@/hooks/player/use-next-episode";
import { useIsTV } from "@/hooks/use-platform";
import { useIsLandscape } from "@/lib/breakpoints";
import { useProfile } from "@/contexts/profile-context";
import { useToast } from "@/components/ui/toast";

// A seek this close to the end of the buffered data still restarts the stream
const BUFFER_MARGIN = 0.5;
// Skips (arrow keys, ±10 buttons) in a row restart the stream once, where they stop
const SKIP_SETTLE_MS = 400;
// Ctrl+← past this far into a chapter restarts it; before, it goes to the previous one
const CHAPTER_RESTART_S = 3;

/** The Settings' subtitle track for this media, until one is picked in the player. */
function defaultSubtitle(tracks: MediaStream[], prefs: Profile["preferences"]): number | null {
  if (!tracks.length || prefs.subtitles_enabled === false || prefs.default_subtitle === "none") {
    return null;
  }
  const inLanguage = tracks.filter((t) => t.language === prefs.default_subtitle);
  const track =
    inLanguage.find((t) => t.is_default) ??
    inLanguage[0] ??
    tracks.find((t) => t.is_default) ??
    tracks[0];
  return track.stream_index;
}

/** The player's size and the picture's shape */
interface FrameBox {
  width: number;
  height: number;
  aspect: number;
}

/** Up next's buttons sit this far above the bottom (next-episode-overlay: bottom-28) */
const UP_NEXT_BOTTOM = 112;

/**
 * Up next's frame: the picture itself (not the bars around it in the player's box, cut
 * off) at 40% of the width, in the bottom left corner, level with the buttons.
 */
function upNextFrame({ width: W, height: H, aspect }: FrameBox) {
  const w = Math.min(W, H * aspect);
  const h = w / aspect;
  const x0 = (W - w) / 2;
  const y0 = (H - h) / 2;
  const scale = (0.4 * W) / w;
  const top = H - UP_NEXT_BOTTOM - h * scale;
  return {
    x: 0.04 * W - x0 * scale,
    y: top - y0 * scale,
    scale,
    clipPath: `inset(${y0}px ${W - x0 - w}px ${H - y0 - h}px ${x0}px round ${12 / scale}px)`,
  };
}

/** On an upright screen: the picture moves up near the top, full width; the next
 * episode's card goes under it */
function upNextTop({ width: W, height: H, aspect }: FrameBox) {
  const w = Math.min(W, H * aspect);
  const h = w / aspect;
  const x0 = (W - w) / 2;
  const y0 = (H - h) / 2;
  return {
    x: 0,
    y: 0.07 * H - y0,
    scale: 1,
    clipPath: `inset(${y0}px ${W - x0 - w}px ${H - y0 - h}px ${x0}px round 0px)`,
  };
}

const FULL_FRAME = { x: 0, y: 0, scale: 1, clipPath: "inset(0px 0px 0px 0px round 0px)" };

function storedNumber(key: string, fallback: number): number {
  if (typeof window === "undefined") return fallback;
  const value = parseFloat(localStorage.getItem(key) ?? "");
  return Number.isFinite(value) ? value : fallback;
}

// Safari's prefixed Fullscreen API (older iPadOS)
type WebkitFullscreen<T> = T & {
  webkitRequestFullscreen?: () => void;
  webkitExitFullscreen?: () => void;
  webkitFullscreenElement?: Element | null;
};

interface VideoPlayerProps {
  mediaId: number;
  title: string;
  subtitle?: string;
  audioTracks: MediaStream[];
  subtitleTracks: MediaStream[];
  initialDuration?: number;
  initialPosition?: number;
  /** Two or more: a segmented seekbar and Ctrl+←/→ to move between them */
  chapters?: Chapter[] | null;
  /** A concert's chapters are songs */
  chapterWord?: "chapter" | "song";
  seriesId?: number | null;
  currentSeason?: number;
  onEpisodeSelect?: (mediaId: number) => void;
  /** A film: Up next offers films of the library at its credits */
  isMovie?: boolean;
  /** Where the credits start (Up next shows there), and the point set by hand */
  creditsStart?: number | null;
  creditsOwn?: number | null;
}

export function VideoPlayer({
  mediaId,
  title,
  subtitle,
  audioTracks,
  subtitleTracks,
  initialDuration,
  initialPosition = 0,
  chapters,
  chapterWord,
  seriesId,
  currentSeason = 1,
  onEpisodeSelect,
  isMovie = false,
  creditsStart = null,
  creditsOwn = null,
}: VideoPlayerProps) {
  const router = useRouter();
  const t = useTranslations();
  const toast = useToast();
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const hideControlsTimeout = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const subtitleRendererRef = useRef<SubtitleRendererHandle>(null);
  const clients = useStreamClients(mediaId, videoRef);
  const episodesButtonRef = useRef<HTMLButtonElement>(null);

  // Core Playback State
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSeeking, setIsSeeking] = useState(false);
  const [currentTime, setCurrentTime] = useState(initialPosition);
  const [duration, setDuration] = useState(initialDuration || 0);
  // Kept across videos and reloads (they reset to full volume every time)
  const [volume, setVolume] = useState(() => storedNumber("player_volume", 1));
  const [isMuted, setIsMuted] = useState(() => storedNumber("player_muted", 0) === 1);
  // The browser refused the sound without a tap (iOS after a reload): playing muted
  const [soundBlocked, setSoundBlocked] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [seekTime, setSeekTime] = useState(initialPosition);
  // Bumped on every seek so seeking to the current target still reloads the stream
  const [seekId, setSeekId] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [episodePickerOpen, setEpisodePickerOpen] = useState(false);
  const [streamError, setStreamError] = useState(false);

  // Pool status monitoring
  const { warning: poolWarning, poolStatus } = usePoolStatus({
    enabled: isPlaying,
    pollInterval: 15000,
  });

  // Custom Hooks
  const { profile } = useProfile();
  const prefs = profile?.preferences ?? {};
  const {
    selectedAudio,
    selectedSubtitle,
    subtitleOffset,
    setSelectedAudio,
    setSelectedSubtitle,
    setSubtitleOffset,
  } = usePlayerPreferences(
    mediaId,
    profile?.id,
    Math.max(0, audioTracks.findIndex((t) => t.language === prefs.default_audio)),
    defaultSubtitle(subtitleTracks, prefs),
  );

  const { videoUrl, streamStartTime, localSeekOffset, applyStreamHeaders } = useVideoSync(
    mediaId,
    selectedAudio,
    seekTime,
    initialPosition,
    seekId,
  );

  useMediaSource(videoRef, videoUrl, applyStreamHeaders);

  useVideoEvents({
    videoRef,
    streamStartTime,
    localSeekOffset,
    initialDuration,
    isSeeking,
    isMuted,
    setIsPlaying,
    setIsLoading,
    setIsSeeking,
    setCurrentTime,
    setDuration,
    onError: () => setStreamError(true),
    // Shown muted, not saved: the preference stays, the browser just wants a tap first
    onAutoMuted: () => {
      setIsMuted(true);
      setSoundBlocked(true);
    },
  });

  // Apply saved subtitle offset when video is ready
  useEffect(() => {
    if (subtitleOffset !== 0 && subtitleRendererRef.current) {
      const timer = setTimeout(() => {
        subtitleRendererRef.current?.setManualOffset(subtitleOffset);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [selectedSubtitle, subtitleOffset]);

  // Actions
  const togglePlay = useCallback(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
    }
  }, [isPlaying]);

  const toggleMute = useCallback(() => {
    if (videoRef.current) {
      const newMuted = !isMuted;
      videoRef.current.muted = newMuted;
      setIsMuted(newMuted);
      setSoundBlocked(false);
      localStorage.setItem("player_muted", newMuted ? "1" : "0");
    }
  }, [isMuted]);

  const handleVolumeChange = useCallback((value: number) => {
    if (videoRef.current) {
      videoRef.current.volume = value;
      // Dragging the slider up after muting must unmute the video too, not just the icon
      videoRef.current.muted = value === 0;
      setVolume(value);
      setIsMuted(value === 0);
      localStorage.setItem("player_volume", String(value));
      localStorage.setItem("player_muted", value === 0 ? "1" : "0");
    }
  }, []);

  // The stored volume, once the element exists (mute is applied when playback syncs)
  useEffect(() => {
    if (videoRef.current) videoRef.current.volume = volume;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pendingSkip = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentTimeRef = useRef(currentTime);
  useEffect(() => {
    currentTimeRef.current = currentTime;
  }, [currentTime]);

  // A new stream means a new request, a new ffmpeg and seconds of rebuffering: when the
  // target is already buffered, just move the playhead
  const seekLocally = useCallback(
    (time: number) => {
      const video = videoRef.current;
      if (!video || isLoading || isSeeking) return false;
      const local = time - streamStartTime;
      for (let i = 0; i < video.buffered.length; i++) {
        if (local >= video.buffered.start(i) && local <= video.buffered.end(i) - BUFFER_MARGIN) {
          video.currentTime = local;
          setCurrentTime(time);
          return true;
        }
      }
      return false;
    },
    [isLoading, isSeeking, streamStartTime],
  );

  const restartStreamAt = useCallback((time: number) => {
    setStreamError(false);
    setIsSeeking(true);
    setIsLoading(true);
    setCurrentTime(time);
    setSeekTime(time);
    setSeekId((id) => id + 1);
  }, []);

  const handleSeek = useCallback(
    (time: number) => {
      if (pendingSkip.current) clearTimeout(pendingSkip.current);
      pendingSkip.current = null;
      if (!seekLocally(time)) restartStreamAt(time);
    },
    [seekLocally, restartStreamAt],
  );

  const skip = useCallback(
    (seconds: number) => {
      const target = Math.max(0, Math.min(currentTimeRef.current + seconds, duration));
      if (!pendingSkip.current && seekLocally(target)) return;
      // Out of the buffer: wait for the skips to stop. isSeeking keeps timeupdate from
      // overwriting the target, so the next skip adds to it
      setIsSeeking(true);
      setCurrentTime(target);
      currentTimeRef.current = target;
      if (pendingSkip.current) clearTimeout(pendingSkip.current);
      pendingSkip.current = setTimeout(() => {
        pendingSkip.current = null;
        restartStreamAt(target);
      }, SKIP_SETTLE_MS);
    },
    [duration, seekLocally, restartStreamAt],
  );

  // Ctrl+→: the next chapter. Ctrl+←: back to the start of this one, or to the previous
  // one within its first seconds (as YouTube does)
  const jumpChapter = useCallback(
    (direction: -1 | 1) => {
      if (!chapters) return;
      const now = currentTimeRef.current;
      // A second of slack: a seek can land on the keyframe just before a chapter's start
      const current = Math.max(0, chapters.filter((c) => c.start <= now + 1).length - 1);
      const restart = now - chapters[current].start > CHAPTER_RESTART_S;
      const index = direction > 0 ? current + 1 : Math.max(0, restart ? current : current - 1);
      if (index >= chapters.length) return;
      handleSeek(chapters[index].start);
      currentTimeRef.current = chapters[index].start; // a second press goes on from here
    },
    [chapters, handleSeek],
  );

  useEffect(
    () => () => {
      if (pendingSkip.current) clearTimeout(pendingSkip.current);
    },
    [],
  );

  const toggleFullscreen = useCallback(() => {
    // Older iPadOS Safari has only the webkit-prefixed API
    const el = containerRef.current as WebkitFullscreen<HTMLDivElement> | null;
    const doc = document as WebkitFullscreen<Document>;
    if (!el) return;
    if (document.fullscreenElement ?? doc.webkitFullscreenElement) {
      void (document.exitFullscreen?.() ?? doc.webkitExitFullscreen?.());
      return;
    }
    // iPhone Safari gives element fullscreen to its own video player only: it refuses
    // ours (silently: the button did nothing). What hides its bars is the home-screen app
    const refused = () => toast(t("player.fullscreenHomeScreen"));
    if (el.requestFullscreen) el.requestFullscreen().catch(refused);
    else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
    else refused();
  }, [t, toast]);

  const handleBack = useCallback(() => {
    router.back(); // the unmount effect below releases the stream
  }, [router]);

  const settingsOpenRef = useRef(settingsOpen);
  useEffect(() => {
    settingsOpenRef.current = settingsOpen;
  }, [settingsOpen]);

  // The controls hide 3 s after the last activity
  const scheduleHide = useCallback(() => {
    if (hideControlsTimeout.current) {
      clearTimeout(hideControlsTimeout.current);
    }
    hideControlsTimeout.current = setTimeout(() => {
      // Read when the timer fires: the state captured 3 s earlier said "playing" after a
      // pause with Space, and the controls hid over a paused video
      if (!videoRef.current?.paused && !settingsOpenRef.current) {
        setShowControls(false);
      }
    }, 3000);
  }, []);

  const handleMouseMove = useCallback(() => {
    setShowControls(true);
    scheduleHide();
  }, [scheduleHide]);

  // Only a mouse moving started the countdown: on a phone or a tablet the controls shown
  // at start stayed until a tap on the picture. Playback starting starts it too
  useEffect(() => {
    if (isPlaying) scheduleHide();
  }, [isPlaying, scheduleHide]);

  // A click on the picture: the mouse plays or pauses; a tap shows or hides the controls
  // (it paused the video, and nothing could hide the controls). On the click, not on
  // pointerup: controls shown at pointerup were under the finger when the tap's click
  // came, and the play button took it (the tap that showed the controls paused the video)
  const lastPointer = useRef("mouse");
  const handleSurface = useCallback(() => {
    if (lastPointer.current === "mouse") togglePlay();
    else if (showControls) setShowControls(false);
    else handleMouseMove();
  }, [togglePlay, showControls, handleMouseMove]);

  const handleAudioChange = useCallback(
    (index: number) => {
      setSelectedAudio(index);
      // A new stream with this track, as a seek: spinner, no stale timeupdate from the
      // old stream (the clock jumped back and could be saved as progress)
      restartStreamAt(currentTimeRef.current);
    },
    [setSelectedAudio, restartStreamAt],
  );

  // Fullscreen listener
  useEffect(() => {
    const onFullscreenChange = () => {
      const doc = document as WebkitFullscreen<Document>;
      setIsFullscreen(!!(document.fullscreenElement ?? doc.webkitFullscreenElement));
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    document.addEventListener("webkitfullscreenchange", onFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      document.removeEventListener("webkitfullscreenchange", onFullscreenChange);
    };
  }, []);

  // Watch Progress Saving
  const { markFinished } = useProgressSaving({ mediaId, currentTime, duration, isPlaying });

  // Release the Telegram clients however the player goes away: back button, browser/OS
  // back, swipe, episode switch (the page remounts the player) or tab close (pagehide).
  // StrictMode's dev-only double mount just releases a stream that hasn't started.
  // Releasing the reader also ends the backend ffmpeg (its input stops).
  useEffect(() => {
    const handlePageHide = () => releaseStream(mediaId);
    window.addEventListener("pagehide", handlePageHide);
    return () => {
      window.removeEventListener("pagehide", handlePageHide);
      releaseStream(mediaId);
    };
  }, [mediaId]);

  // ponytail: temporary diagnostics. iOS Safari reloads the player page after about a
  // minute with the video stuck, and an iPhone can't be inspected from here: the state
  // goes to the backend log ([DIAG]) every 5 s and on every media event. Remove when found.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const started = performance.now();
    const send = (event: string) => {
      const buffered = [];
      for (let i = 0; i < video.buffered.length; i++) {
        buffered.push([+video.buffered.start(i).toFixed(1), +video.buffered.end(i).toFixed(1)]);
      }
      const body = JSON.stringify({
        event,
        media: mediaId,
        up: Math.round((performance.now() - started) / 1000),
        t: +video.currentTime.toFixed(1),
        paused: video.paused,
        muted: video.muted,
        rs: video.readyState,
        ns: video.networkState,
        buf: buffered,
        err: video.error ? `${video.error.code} ${video.error.message}` : null,
        hidden: document.hidden,
        ua: navigator.userAgent.slice(13, 60),
      });
      fetch("/api/v1/stream/diag", { method: "POST", body, keepalive: true }).catch(() => {});
    };
    const events = ["waiting", "stalled", "pause", "play", "playing", "error", "emptied", "abort", "suspend", "volumechange"];
    const onEvent = (e: Event) => send(e.type);
    events.forEach((name) => video.addEventListener(name, onEvent));
    const onError = (e: ErrorEvent | PromiseRejectionEvent) =>
      send(`js: ${"message" in e ? e.message : String(e.reason)}`.slice(0, 300));
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onError);
    const timer = setInterval(() => send("tick"), 5000);
    return () => {
      clearInterval(timer);
      events.forEach((name) => video.removeEventListener(name, onEvent));
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onError);
    };
  }, [mediaId]);

  const isTV = useIsTV();
  const landscape = useIsLandscape();

  // Measured when the picture's shape is known and whenever the player resizes
  const [frameBox, setFrameBox] = useState<FrameBox | null>(null);
  useEffect(() => {
    const box = containerRef.current;
    const video = videoRef.current;
    if (!box || !video) return;
    const measure = () => {
      if (!video.videoWidth) return;
      setFrameBox({
        width: box.clientWidth,
        height: box.clientHeight,
        aspect: video.videoWidth / video.videoHeight,
      });
    };
    const observer = new ResizeObserver(measure);
    observer.observe(box);
    video.addEventListener("loadedmetadata", measure);
    return () => {
      observer.disconnect();
      video.removeEventListener("loadedmetadata", measure);
    };
  }, []);
  const controlsVisible = showControls || !isPlaying || isLoading || isSeeking || settingsOpen;

  const togglePiP = useCallback(async () => {
    const video = videoRef.current;
    if (!video) return;
    if (document.pictureInPictureElement) {
      await document.exitPictureInPicture();
    } else if (document.pictureInPictureEnabled) {
      await video.requestPictureInPicture();
    }
  }, []);

  // Where the credits start; admins set it at the current time from the settings menu
  const isAdmin = !!useAuth().user?.is_admin;
  const [credits, setCredits] = useState({ start: creditsStart, own: creditsOwn });
  const creditsControl = isAdmin
    ? {
        own: credits.own,
        setHere: () => {
          const at = Math.floor(currentTimeRef.current);
          setCreditsStart(mediaId, at).then(() => setCredits({ start: at, own: at }));
        },
        // Back to the 30 s before the end until a reload finds a chapter or the series'
        clear: () => {
          setCreditsStart(mediaId, null).then(() => setCredits({ start: null, own: null }));
        },
      }
    : undefined;

  // Up next: the next episode, or after a film the library's recommendations
  const { nextEpisode, recommendations, showNextOverlay, cancelNextOverlay } = useNextEpisode({
    mediaId,
    isEpisode: !!seriesId && !!onEpisodeSelect,
    isMovie,
    currentTime,
    duration,
    creditsStart: credits.start,
  });

  // Up next on screen: the player's own controls step aside (its buttons are the controls),
  // and a click on the small video goes back to the credits, full screen
  const upNext = showNextOverlay && (!!nextEpisode || recommendations.length > 0);
  const upNextImage = nextEpisode
    ? getTmdbImageUrl(nextEpisode.still_path ?? nextEpisode.backdrop_path, "original")
    : getTmdbImageUrl(recommendations[0]?.backdrop_path ?? null, "original");

  useVideoHotkeys({
    togglePlay,
    toggleFullscreen,
    toggleMute,
    skip,
    jumpChapter: chapters && chapters.length > 1 ? jumpChapter : undefined,
    onActivity: handleMouseMove,
    // Up next's buttons are the controls on screen: the TV remote's arrows move between
    // them and OK presses them (as hidden controls, arrows sought and closed it)
    controlsVisible: controlsVisible || upNext,
    isTV,
  });

  // Moving on counts this one as watched
  const playNextEpisode = useCallback(() => {
    if (nextEpisode && onEpisodeSelect) {
      markFinished();
      onEpisodeSelect(nextEpisode.id);
    }
  }, [nextEpisode, onEpisodeSelect, markFinished]);

  const playRecommendation = useCallback(
    (id: number) => {
      markFinished();
      router.replace(`/watch/${id}`);
    },
    [markFinished, router],
  );

  const touchStartRef = useRef<{ x: number; y: number } | null>(null);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    const t = e.touches[0];
    touchStartRef.current = { x: t.clientX, y: t.clientY };
  }, []);

  const handleTouchEnd = useCallback(
    (e: React.TouchEvent) => {
      const start = touchStartRef.current;
      if (!start) return;
      const t = e.changedTouches[0];
      const dx = t.clientX - start.x;
      const dy = Math.abs(t.clientY - start.y);
      // Swipe right ≥80px starting from left edge (first 40px) and mostly horizontal
      if (dx >= 80 && dy < 60 && start.x < 40) {
        router.back();
      }
      touchStartRef.current = null;
    },
    [router],
  );

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full bg-black"
      // Pointer, not mouse, events: a tap's emulated mousemove re-showed the controls
      onPointerMove={(e) => e.pointerType === "mouse" && handleMouseMove()}
      // A touch anywhere, a button too, restarts the countdown (the tap on the picture
      // itself shows or hides them: handleSurface)
      onPointerDownCapture={(e) => {
        lastPointer.current = e.pointerType;
        if (e.pointerType !== "mouse") scheduleHide();
      }}
      onMouseLeave={() => isPlaying && !settingsOpen && setShowControls(false)}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      style={{ cursor: showControls ? "default" : "none" }}
    >
      {seriesId && onEpisodeSelect && (
        <EpisodePicker
          open={episodePickerOpen}
          seriesId={seriesId}
          currentMediaId={mediaId}
          currentSeason={currentSeason}
          onClose={() => setEpisodePickerOpen(false)}
          onEpisodeSelect={onEpisodeSelect}
          toggleButtonRef={episodesButtonRef}
        />
      )}

      <PoolWarningOverlay
        warning={poolWarning}
        poolPressure={poolStatus?.pool_pressure}
      />

      {soundBlocked && (
        // A phone has no mute button (its keys set the volume): this is where the tap
        // the browser wants goes
        <DSButton
          variant="secondary"
          icon={<VolumeX className="h-4 w-4" />}
          onClick={() => {
            if (videoRef.current) videoRef.current.muted = false;
            setIsMuted(false);
            setSoundBlocked(false);
          }}
          className="absolute top-20 right-4 z-30"
        >
          {t("player.tapForSound")}
        </DSButton>
      )}

      <UpNextBackdrop image={upNextImage} visible={upNext && landscape} />

      {/* Video + subtitles. Up next shrinks them into the bottom left corner, over the next
          episode's picture; on an upright screen they move up instead, over its card */}
      <motion.div
        className="absolute inset-0 flex items-center overflow-hidden"
        style={{ transformOrigin: "0 0" }}
        initial={false}
        animate={
          upNext && frameBox
            ? landscape
              ? upNextFrame(frameBox)
              : upNextTop(frameBox)
            : FULL_FRAME
        }
        transition={{ duration: 0.55, ease: [0.4, 0, 0.2, 1] }}
      >
        <div className="relative w-full h-full overflow-hidden">
          <video
            ref={videoRef}
            className="absolute inset-0 w-full h-full"
            onClick={upNext ? cancelNextOverlay : handleSurface}
            playsInline
            autoPlay
          />

          <SubtitleRenderer
            ref={subtitleRendererRef}
            videoRef={videoRef}
            mediaId={mediaId}
            subtitleTrack={selectedSubtitle}
            pgs={
              subtitleTracks.find((s) => s.stream_index === selectedSubtitle)?.codec_name ===
              "hdmv_pgs_subtitle"
            }
            enabled={selectedSubtitle !== null}
            visible={!isLoading && !isSeeking}
            timeOffset={streamStartTime}
            initialManualOffset={subtitleOffset}
          />
        </div>
      </motion.div>

      {streamError && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-4 bg-black/70 px-4 text-center">
          <p className="text-white text-lg">{t("player.streamError")}</p>
          <DSButton autoFocus onClick={() => restartStreamAt(currentTimeRef.current)}>
            {t("common.retry")}
          </DSButton>
        </div>
      )}

      <NextEpisodeOverlay
        nextEpisode={nextEpisode}
        recommendations={recommendations}
        onPick={playRecommendation}
        visible={showNextOverlay}
        isPlaying={isPlaying}
        isEnded={!isPlaying && duration > 0 && currentTime >= duration - 1}
        onPlay={playNextEpisode}
        onCancel={cancelNextOverlay}
      />

      <PlayerControls
        visible={controlsVisible && !upNext}
        isPlaying={isPlaying}
        isLoading={isLoading || isSeeking}
        currentTime={currentTime}
        duration={duration}
        chapters={chapters}
        chapterWord={chapterWord}
        clients={clients}
        volume={volume}
        isMuted={isMuted}
        isFullscreen={isFullscreen}
        title={title}
        subtitle={subtitle}
        audioTracks={audioTracks}
        subtitleTracks={subtitleTracks}
        selectedAudio={selectedAudio}
        selectedSubtitle={selectedSubtitle}
        subtitleOffset={subtitleOffset}
        onTogglePlay={togglePlay}
        onSeek={handleSeek}
        onVolumeChange={handleVolumeChange}
        onToggleMute={toggleMute}
        onToggleFullscreen={toggleFullscreen}
        // Opened from the home screen, iOS shows the app full screen already
        canFullscreen={
          typeof navigator !== "undefined" &&
          !(navigator as Navigator & { standalone?: boolean }).standalone
        }
        onSurfaceClick={handleSurface}
        onBack={handleBack}
        onAudioChange={handleAudioChange}
        onSubtitleChange={setSelectedSubtitle}
        onSubtitleOffsetChange={setSubtitleOffset}
        onSkip={skip}
        onActivity={handleMouseMove}
        onSettingsOpenChange={setSettingsOpen}
        credits={creditsControl}
        hasEpisodes={!!seriesId && !!onEpisodeSelect}
        episodePickerOpen={episodePickerOpen}
        onToggleEpisodes={() => setEpisodePickerOpen((v) => !v)}
        episodesButtonRef={episodesButtonRef}
        onTogglePiP={
          !isTV && typeof document !== "undefined" && document.pictureInPictureEnabled
            ? togglePiP
            : undefined
        }
        isTV={isTV}
      />
    </div>
  );
}
