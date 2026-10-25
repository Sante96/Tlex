"use client";

import { useState, useCallback } from "react";

interface PlayerPreferences {
  selectedAudio: number;
  selectedSubtitle: number | null;
  /** False until a subtitle track (or "off") was picked for this media */
  subtitleChosen: boolean;
  subtitleOffset: number;
  setSelectedAudio: (index: number) => void;
  setSelectedSubtitle: (index: number | null) => void;
  setSubtitleOffset: (offset: number) => void;
}

const SUBTITLE_OFF = "off";

/**
 * Per-media player choices, persisted in localStorage.
 * defaultAudio is used until an audio track is picked for this media.
 */
export function usePlayerPreferences(
  mediaId: number,
  defaultAudio = 0,
): PlayerPreferences {
  // Load saved preferences from localStorage
  const [selectedAudio, setSelectedAudioState] = useState(() => {
    if (typeof window === "undefined") return defaultAudio;
    const saved = localStorage.getItem(`player_audio_${mediaId}`);
    return saved ? parseInt(saved, 10) : defaultAudio;
  });

  // undefined = never chosen, null = explicitly off
  const [selectedSubtitle, setSelectedSubtitleState] = useState<
    number | null | undefined
  >(() => {
    if (typeof window === "undefined") return undefined;
    const saved = localStorage.getItem(`player_subtitle_${mediaId}`);
    if (saved === null) return undefined;
    return saved === SUBTITLE_OFF ? null : parseInt(saved, 10);
  });

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
      // Store "off" too: removing the key made the auto-select turn subtitles back on
      localStorage.setItem(
        `player_subtitle_${mediaId}`,
        index === null ? SUBTITLE_OFF : String(index),
      );
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
    selectedSubtitle: selectedSubtitle ?? null,
    subtitleChosen: selectedSubtitle !== undefined,
    subtitleOffset,
    setSelectedAudio,
    setSelectedSubtitle,
    setSubtitleOffset,
  };
}
