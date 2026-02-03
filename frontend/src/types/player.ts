import type { MediaStream } from "./api";

export interface PlayerState {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  isFullscreen: boolean;
  showControls: boolean;
  isBuffering: boolean;
}

export interface PlayerTracks {
  audioTracks: MediaStream[];
  subtitleTracks: MediaStream[];
  selectedAudio: number;
  selectedSubtitle: number | null;
}

export interface PlayerActions {
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  seek: (time: number) => void;
  setVolume: (volume: number) => void;
  toggleMute: () => void;
  toggleFullscreen: () => void;
  selectAudioTrack: (index: number) => void;
  selectSubtitleTrack: (index: number | null) => void;
}

export type PlayerContextValue = PlayerState & PlayerTracks & PlayerActions;
