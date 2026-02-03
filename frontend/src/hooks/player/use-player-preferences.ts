"use client";

import { useState, useCallback } from "react";

interface PlayerPreferences {
  selectedAudio: number;
  selectedSubtitle: number | null;
  subtitleOffset: number;
  setSelectedAudio: (index: number) => void;
  setSelectedSubtitle: (index: number | null) => void;
  setSubtitleOffset: (offset: number) => void;
}

export function usePlayerPreferences(mediaId: number): PlayerPreferences {
  // Load saved preferences from localStorage
  const [selectedAudio, setSelectedAudioState] = useState(() => {
    if (typeof window === "undefined") return 0;
    const saved = localStorage.getItem(`player_audio_${mediaId}`);
    return saved ? parseInt(saved, 10) : 0;
  });

  const [selectedSubtitle, setSelectedSubtitleState] = useState<number | null>(
    () => {
      if (typeof window === "undefined") return null;
      const saved = localStorage.getItem(`player_subtitle_${mediaId}`);
      return saved ? parseInt(saved, 10) : null;
    },
  );

  const [subtitleOffset, setSubtitleOffsetState] = useState(() => {
    if (typeof window === "undefined") return 0;
    const saved = localStorage.getItem(`player_suboffset_${mediaId}`);
    return saved ? parseFloat(saved) : 0;
  });

  const setSelectedAudio = useCallback(
    (index: number) => {
      setSelectedAudioState(index);
      localStorage.setItem(`player_audio_${mediaId}`, String(index));
    },
    [mediaId],
  );

  const setSelectedSubtitle = useCallback(
    (index: number | null) => {
      setSelectedSubtitleState(index);
      if (index !== null) {
        localStorage.setItem(`player_subtitle_${mediaId}`, String(index));
      } else {
        localStorage.removeItem(`player_subtitle_${mediaId}`);
      }
    },
    [mediaId],
  );

  const setSubtitleOffset = useCallback(
    (offset: number) => {
      setSubtitleOffsetState(offset);
      localStorage.setItem(`player_suboffset_${mediaId}`, String(offset));
    },
    [mediaId],
  );

  return {
    selectedAudio,
    selectedSubtitle,
    subtitleOffset,
    setSelectedAudio,
    setSelectedSubtitle,
    setSubtitleOffset,
  };
}
