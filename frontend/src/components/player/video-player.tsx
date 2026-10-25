"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import { DSButton } from "@/components/ds";
import { useRouter } from "next/navigation";
import { PlayerControls } from "./player-controls";
import {
  SubtitleRenderer,
  type SubtitleRendererHandle,
} from "./subtitle-renderer";
import { releaseStream, type Chapter, type MediaStream, type Profile } from "@/lib/api";

import { usePlayerPreferences } from "@/hooks/player/use-player-preferences";
import { usePoolStatus } from "@/hooks/player/use-pool-status";
import { useVideoSync } from "@/hooks/player/use-video-sync";
import { useMediaSource } from "@/hooks/player/use-media-source";
import { useVideoEvents } from "@/hooks/player/use-video-events";
import { useVideoHotkeys } from "@/hooks/player/use-video-hotkeys";
import { useProgressSaving } from "@/hooks/player/use-progress-saving";
import { PoolWarningOverlay } from "./pool-warning";
import { EpisodePicker } from "./episode-picker";
import { NextEpisodeOverlay } from "./next-episode-overlay";
import { useNextEpisode } from "@/hooks/player/use-next-episode";
import { useIsMobile } from "@/lib/breakpoints";
import { useIsTV } from "@/hooks/use-platform";
import { useProfile } from "@/contexts/profile-context";

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

function storedNumber(key: string, fallback: number): number {
  if (typeof window === "undefined") return fallback;
  const value = parseFloat(localStorage.getItem(key) ?? "");
  return Number.isFinite(value) ? value : fallback;
}

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
  seriesId?: number | null;
  currentSeason?: number;
  onEpisodeSelect?: (mediaId: number) => void;
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
  seriesId,
  currentSeason = 1,
  onEpisodeSelect,
}: VideoPlayerProps) {
  const router = useRouter();
  const t = useTranslations();
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const hideControlsTimeout = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const subtitleRendererRef = useRef<SubtitleRendererHandle>(null);
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
    // iPhone Safari has no element fullscreen: requestFullscreen is undefined there
    if (!containerRef.current || !document.fullscreenEnabled) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      containerRef.current.requestFullscreen().catch(() => {});
    }
  }, []);

  const handleBack = useCallback(() => {
    router.back(); // the unmount effect below releases the stream
  }, [router]);

  const settingsOpenRef = useRef(settingsOpen);
  useEffect(() => {
    settingsOpenRef.current = settingsOpen;
  }, [settingsOpen]);

  const handleMouseMove = useCallback(() => {
    setShowControls(true);
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

  // A click on the picture: the mouse plays or pauses; a tap shows or hides the controls
  // (it paused the video, and nothing could hide the controls)
  const handleSurface = useCallback(
    (e: React.PointerEvent) => {
      if (e.pointerType === "mouse") togglePlay();
      else if (showControls) setShowControls(false);
      else handleMouseMove();
    },
    [togglePlay, showControls, handleMouseMove],
  );

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
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () =>
      document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, []);

  // Watch Progress Saving
  useProgressSaving({ mediaId, currentTime, duration, isPlaying });

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

  const isMobile = useIsMobile();
  const isTV = useIsTV();
  const controlsVisible = showControls || !isPlaying || isLoading || isSeeking || settingsOpen;

  useVideoHotkeys({
    togglePlay,
    toggleFullscreen,
    toggleMute,
    skip,
    jumpChapter: chapters && chapters.length > 1 ? jumpChapter : undefined,
    onActivity: handleMouseMove,
    controlsVisible,
    isTV,
  });

  const togglePiP = useCallback(async () => {
    const video = videoRef.current;
    if (!video) return;
    if (document.pictureInPictureElement) {
      await document.exitPictureInPicture();
    } else if (document.pictureInPictureEnabled) {
      await video.requestPictureInPicture();
    }
  }, []);

  // Next episode auto-play
  const { nextEpisode, showNextOverlay, cancelNextOverlay } = useNextEpisode({
    mediaId,
    isEpisode: !!seriesId && !!onEpisodeSelect,
    currentTime,
    duration,
  });

  const playNextEpisode = useCallback(() => {
    if (nextEpisode && onEpisodeSelect) {
      onEpisodeSelect(nextEpisode.id);
    }
  }, [nextEpisode, onEpisodeSelect]);

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

      {/* Video + subtitles — shrinks left when next episode panel slides in */}
      <motion.div
        className="absolute top-0 left-0 bottom-0 flex items-center overflow-hidden"
        initial={false}
        animate={{
          width: showNextOverlay && !isMobile ? "62%" : "100%",
          borderRadius: showNextOverlay && !isMobile ? "8px" : "0px",
        }}
        transition={{ duration: 0.45, ease: [0.4, 0, 0.2, 1] }}
      >
        <div
          className={`relative w-full overflow-hidden ${showNextOverlay && !isMobile ? "aspect-video" : "h-full"}`}
        >
          <video
            ref={videoRef}
            className="absolute inset-0 w-full h-full"
            onPointerUp={handleSurface}
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
        visible={showNextOverlay}
        isPlaying={isPlaying}
        isEnded={!isPlaying && duration > 0 && currentTime >= duration - 1}
        onPlay={playNextEpisode}
        onCancel={cancelNextOverlay}
      />

      <PlayerControls
        visible={controlsVisible}
        isPlaying={isPlaying}
        isLoading={isLoading || isSeeking}
        currentTime={currentTime}
        duration={duration}
        chapters={chapters}
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
        canFullscreen={typeof document !== "undefined" && document.fullscreenEnabled}
        onSurfacePointerUp={handleSurface}
        onBack={handleBack}
        onAudioChange={handleAudioChange}
        onSubtitleChange={setSelectedSubtitle}
        onSubtitleOffsetChange={setSubtitleOffset}
        onSkip={skip}
        onActivity={handleMouseMove}
        onSettingsOpenChange={setSettingsOpen}
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
