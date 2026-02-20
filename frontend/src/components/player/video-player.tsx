"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { PlayerControls } from "./player-controls";
import {
  SubtitleRenderer,
  type SubtitleRendererHandle,
} from "./subtitle-renderer";
import { releaseStream, type MediaStream } from "@/lib/api";

import { usePlayerPreferences } from "@/hooks/player/use-player-preferences";
import { usePoolStatus } from "@/hooks/player/use-pool-status";
import { useVideoSync } from "@/hooks/player/use-video-sync";
import { useVideoEvents } from "@/hooks/player/use-video-events";
import { useVideoHotkeys } from "@/hooks/player/use-video-hotkeys";
import { useProgressSaving } from "@/hooks/player/use-progress-saving";
import { PoolWarningOverlay } from "./pool-warning";
import { EpisodePicker } from "./episode-picker";
import { NextEpisodeOverlay } from "./next-episode-overlay";
import { useNextEpisode } from "@/hooks/player/use-next-episode";

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
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [episodePickerOpen, setEpisodePickerOpen] = useState(false);

  // Pool status monitoring
  const { warning: poolWarning, poolStatus } = usePoolStatus({
    enabled: isPlaying,
    pollInterval: 15000,
  });

  // Custom Hooks
  const {
    selectedAudio,
    selectedSubtitle,
    subtitleOffset,
    setSelectedAudio,
    setSelectedSubtitle,
    setSubtitleOffset,
  } = usePlayerPreferences(mediaId);

  // Auto-select first subtitle track if none saved
  useEffect(() => {
    if (selectedSubtitle === null && subtitleTracks.length > 0) {
      const defaultTrack = subtitleTracks.find((t) => t.is_default);
      setSelectedSubtitle(
        defaultTrack?.stream_index ?? subtitleTracks[0].stream_index,
      );
    }
  }, [selectedSubtitle, subtitleTracks, setSelectedSubtitle]);

  const { videoUrl, streamStartTime, localSeekOffset } = useVideoSync(
    mediaId,
    selectedAudio,
    seekTime,
    initialPosition,
  );

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

  const handleSeek = useCallback((time: number) => {
    setIsSeeking(true);
    setIsLoading(true);
    setCurrentTime(time);
    setSeekTime(time);
  }, []);

  const skip = useCallback(
    (seconds: number) => {
      const newTime = Math.max(0, Math.min(currentTime + seconds, duration));
      handleSeek(newTime);
    },
    [currentTime, duration, handleSeek],
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
    releaseStream(mediaId);
    router.back();
  }, [router, mediaId]);

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

  // Release Telegram stream clients on tab/browser close (pagehide)
  // Note: don't use useEffect cleanup — React StrictMode in dev triggers spurious unmounts
  // For SPA navigation, releaseStream is called in handleBack instead
  useEffect(() => {
    const handlePageHide = () => releaseStream(mediaId);
    window.addEventListener("pagehide", handlePageHide);
    return () => window.removeEventListener("pagehide", handlePageHide);
  }, [mediaId]);

  useVideoHotkeys({
    togglePlay,
    toggleFullscreen,
    toggleMute,
    skip,
  });

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

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full bg-black"
      onMouseMove={handleMouseMove}
      onMouseLeave={() => isPlaying && !settingsOpen && setShowControls(false)}
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
          width: showNextOverlay ? "62%" : "100%",
          borderRadius: showNextOverlay ? "8px" : "0px",
        }}
        transition={{ duration: 0.45, ease: [0.4, 0, 0.2, 1] }}
      >
        <div
          className={`relative w-full overflow-hidden ${showNextOverlay ? "aspect-video" : "h-full"}`}
        >
          <video
            ref={videoRef}
            src={videoUrl}
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
        onSettingsOpenChange={setSettingsOpen}
        hasEpisodes={!!seriesId && !!onEpisodeSelect}
        episodePickerOpen={episodePickerOpen}
        onToggleEpisodes={() => setEpisodePickerOpen((v) => !v)}
        episodesButtonRef={episodesButtonRef}
      />
    </div>
  );
}
