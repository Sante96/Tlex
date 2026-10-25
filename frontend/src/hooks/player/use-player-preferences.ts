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

const SUBTITLE_OFF = "off";

function saved(key: string): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(key);
}

/**
 * Per-media player choices, persisted in localStorage. Until a track is picked in the
 * player for this media, the profile's Settings decide (defaultAudio, defaultSubtitle),
 * recomputed on every render: a profile that loads late, or Settings changed later, still
 * apply. Only a pick in the player is stored.
 */
export function usePlayerPreferences(
  mediaId: number,
  defaultAudio = 0,
  defaultSubtitle: number | null = null,
): PlayerPreferences {
  const [audio, setAudio] = useState(() => {
    const value = saved(`player_audio_${mediaId}`);
    return value === null ? undefined : parseInt(value, 10);
  });

  // undefined = never chosen, null = explicitly off
  const [subtitle, setSubtitle] = useState<number | null | undefined>(() => {
    const value = saved(`player_subtitle_${mediaId}`);
    if (value === null) return undefined;
    return value === SUBTITLE_OFF ? null : parseInt(value, 10);
  });

  const [subtitleOffset, setSubtitleOffsetState] = useState(() =>
    parseFloat(saved(`player_suboffset_${mediaId}`) ?? "0"),
  );

  const setSelectedAudio = useCallback(
    (index: number) => {
      setAudio(index);
      localStorage.setItem(`player_audio_${mediaId}`, String(index));
    },
    [mediaId],
  );

  const setSelectedSubtitle = useCallback(
    (index: number | null) => {
      setSubtitle(index);
      // Store "off" too, or the Settings default would turn subtitles back on
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
    selectedAudio: audio ?? defaultAudio,
    selectedSubtitle: subtitle === undefined ? defaultSubtitle : subtitle,
    subtitleOffset,
    setSelectedAudio,
    setSelectedSubtitle,
    setSubtitleOffset,
  };
}
