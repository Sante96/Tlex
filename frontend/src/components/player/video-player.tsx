"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { PlayerControls } from "./player-controls";
import {
  SubtitleRenderer,
  type SubtitleRendererHandle,
} from "./subtitle-renderer";
import { releaseStream, type MediaStream, type Profile } from "@/lib/api";

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

interface VideoPlayerProps {
  mediaId: number;
  title: string;
  subtitle?: string;
  audioTracks: MediaStream[];
  subtitleTracks: MediaStream[];
  initialDuration?: number;
  initialPosition?: number;
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
  seriesId,
  currentSeason = 1,
  onEpisodeSelect,
}: VideoPlayerProps) {
  const router = useRouter();
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
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [seekTime, setSeekTime] = useState(initialPosition);
  // Bumped on every seek so seeking to the current target still reloads the stream
  const [seekId, setSeekId] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [episodePickerOpen, setEpisodePickerOpen] = useState(false);

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
    Math.max(0, audioTracks.findIndex((t) => t.language === prefs.default_audio)),
    defaultSubtitle(subtitleTracks, prefs),
  );

  const { videoUrl, streamStartTime, localSeekOffset } = useVideoSync(
    mediaId,
    selectedAudio,
    seekTime,
    initialPosition,
    seekId,
  );

  useMediaSource(videoRef, videoUrl);

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
    }
  }, [isMuted]);

  const handleVolumeChange = useCallback((value: number) => {
    if (videoRef.current) {
      videoRef.current.volume = value;
      setVolume(value);
      setIsMuted(value === 0);
    }
  }, []);

  const pendingSkip = useRef<ReturnType<typeof setTimeout> | null>(null);

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
      const target = Math.max(0, Math.min(currentTime + seconds, duration));
      if (!pendingSkip.current && seekLocally(target)) return;
      // Out of the buffer: wait for the skips to stop. isSeeking keeps timeupdate from
      // overwriting the target, so the next skip adds to it
      setIsSeeking(true);
      setCurrentTime(target);
      if (pendingSkip.current) clearTimeout(pendingSkip.current);
      pendingSkip.current = setTimeout(() => {
        pendingSkip.current = null;
        restartStreamAt(target);
      }, SKIP_SETTLE_MS);
    },
    [currentTime, duration, seekLocally, restartStreamAt],
  );

  useEffect(
    () => () => {
      if (pendingSkip.current) clearTimeout(pendingSkip.current);
    },
    [],
  );

  const toggleFullscreen = useCallback(() => {
    if (!containerRef.current) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      containerRef.current.requestFullscreen();
    }
  }, []);

  const handleBack = useCallback(() => {
    router.back(); // the unmount effect below releases the stream
  }, [router]);

  const handleMouseMove = useCallback(() => {
    setShowControls(true);
    if (hideControlsTimeout.current) {
      clearTimeout(hideControlsTimeout.current);
    }
    hideControlsTimeout.current = setTimeout(() => {
      if (isPlaying && !settingsOpen) {
        setShowControls(false);
      }
    }, 3000);
  }, [isPlaying, settingsOpen]);

  const handleAudioChange = useCallback(
    (index: number) => {
      setSeekTime(currentTime);
      setSelectedAudio(index);
    },
    [currentTime, setSelectedAudio],
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

  useVideoHotkeys({
    togglePlay,
    toggleFullscreen,
    toggleMute,
    skip,
    onActivity: handleMouseMove,
  });

  const isMobile = useIsMobile();
  const isTV = useIsTV();

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
      onMouseMove={handleMouseMove}
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
            onClick={togglePlay}
            playsInline
            autoPlay
          />

          <SubtitleRenderer
            ref={subtitleRendererRef}
            videoRef={videoRef}
            mediaId={mediaId}
            subtitleTrack={selectedSubtitle}
            enabled={selectedSubtitle !== null}
            visible={!isLoading && !isSeeking}
            timeOffset={streamStartTime}
            initialManualOffset={subtitleOffset}
          />
        </div>
      </motion.div>

      <NextEpisodeOverlay
        nextEpisode={nextEpisode}
        visible={showNextOverlay}
        isPlaying={isPlaying}
        isEnded={!isPlaying && duration > 0 && currentTime >= duration - 1}
        onPlay={playNextEpisode}
        onCancel={cancelNextOverlay}
      />

      <PlayerControls
        visible={showControls || isLoading || isSeeking || settingsOpen}
        isPlaying={isPlaying}
        isLoading={isLoading || isSeeking}
        currentTime={currentTime}
        duration={duration}
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
