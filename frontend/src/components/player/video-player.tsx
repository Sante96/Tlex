"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { PlayerControls } from "./player-controls";
import {
  SubtitleRenderer,
  type SubtitleRendererHandle,
} from "./subtitle-renderer";
import { updateWatchProgress, type MediaStream } from "@/lib/api";

import { usePlayerPreferences } from "@/hooks/player/use-player-preferences";
import { useVideoSync } from "@/hooks/player/use-video-sync";
import { useVideoEvents } from "@/hooks/player/use-video-events";
import { useVideoHotkeys } from "@/hooks/player/use-video-hotkeys";

interface VideoPlayerProps {
  mediaId: number;
  title: string;
  subtitle?: string;
  audioTracks: MediaStream[];
  subtitleTracks: MediaStream[];
  initialDuration?: number;
  initialPosition?: number;
}

export function VideoPlayer({
  mediaId,
  title,
  subtitle,
  audioTracks,
  subtitleTracks,
  initialDuration,
  initialPosition = 0,
}: VideoPlayerProps) {
  const router = useRouter();
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const hideControlsTimeout = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const subtitleRendererRef = useRef<SubtitleRendererHandle>(null);

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

  // Custom Hooks
  const {
    selectedAudio,
    selectedSubtitle,
    subtitleOffset,
    setSelectedAudio,
    setSelectedSubtitle,
    setSubtitleOffset,
  } = usePlayerPreferences(mediaId);

  const { videoUrl, streamStartTime, isWarmed } = useVideoSync(
    mediaId,
    selectedAudio,
    seekTime,
    initialPosition,
  );

  useVideoEvents({
    videoRef,
    streamStartTime,
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
    router.back();
  }, [router]);

  const handleMouseMove = useCallback(() => {
    setShowControls(true);
    if (hideControlsTimeout.current) {
      clearTimeout(hideControlsTimeout.current);
    }
    hideControlsTimeout.current = setTimeout(() => {
      if (isPlaying) {
        setShowControls(false);
      }
    }, 3000);
  }, [isPlaying]);

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
  const lastSavedRef = useRef(0);
  const currentTimeRef = useRef(currentTime);
  const durationRef = useRef(duration);

  useEffect(() => {
    currentTimeRef.current = currentTime;
    durationRef.current = duration;
  });

  useEffect(() => {
    const interval = setInterval(() => {
      if (
        isPlaying &&
        currentTime > 0 &&
        duration > 0 &&
        currentTime - lastSavedRef.current >= 10
      ) {
        lastSavedRef.current = currentTime;
        updateWatchProgress(
          mediaId,
          Math.floor(currentTime),
          Math.floor(duration),
        ).catch(() => {});
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [isPlaying, currentTime, duration, mediaId]);

  useEffect(() => {
    const saveProgress = () => {
      const time = currentTimeRef.current;
      const dur = durationRef.current;
      if (time > 0 && dur > 0) {
        updateWatchProgress(mediaId, Math.floor(time), Math.floor(dur)).catch(
          () => {},
        );
      }
    };

    if (!isPlaying) saveProgress();

    const handleBeforeUnload = () => saveProgress();
    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      saveProgress();
    };
  }, [isPlaying, mediaId]);

  useVideoHotkeys({
    togglePlay,
    toggleFullscreen,
    toggleMute,
    skip,
  });

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full bg-black"
      onMouseMove={handleMouseMove}
      onMouseLeave={() => isPlaying && setShowControls(false)}
      style={{ cursor: showControls ? "default" : "none" }}
    >
      <video
        ref={videoRef}
        src={videoUrl}
        className="w-full h-full"
        onClick={togglePlay}
        playsInline
        autoPlay
      />

      <SubtitleRenderer
        ref={subtitleRendererRef}
        videoRef={videoRef}
        mediaId={mediaId}
        subtitleTrack={selectedSubtitle}
        enabled={selectedSubtitle !== null && !isLoading}
        timeOffset={streamStartTime}
        initialManualOffset={subtitleOffset}
      />

      <PlayerControls
        visible={showControls || isLoading || isSeeking}
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
      />
    </div>
  );
}
