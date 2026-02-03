// Re-export everything from modules
export { api, API_BASE_URL } from "./client";

// Auth
export { login, register, getCurrentUser } from "./auth";
export type { LoginResponse, UserResponse } from "./auth";

// Media
export {
  getMediaList,
  getMediaDetails,
  deleteMedia,
  refreshMetadata,
  getMediaCast,
  getMediaEpisodes,
  triggerScan,
  getScanStatus,
} from "./media";
export type {
  MediaItem,
  MediaStream,
  MediaDetails,
  CastMember,
  EpisodeInfo,
} from "./media";

// Series
export {
  getSeriesList,
  getSeriesDetails,
  refreshSeriesMetadata,
  getSeriesCast,
} from "./series";
export type {
  SeriesItem,
  SeasonInfo,
  SeriesDetails,
  EpisodeWatchProgress,
} from "./series";

// Progress
export {
  getWatchProgress,
  updateWatchProgress,
  getContinueWatching,
} from "./progress";
export type { WatchProgress, ContinueWatchingItem } from "./progress";

// Profiles
export {
  getProfiles,
  getProfile,
  createProfile,
  updateProfile,
  deleteProfile,
} from "./profiles";
export type { Profile, ProfileListResponse } from "./profiles";

// Stream & Subtitles
export {
  getStreamUrl,
  getSubtitleUrl,
  getSubtitleTracks,
  warmStream,
} from "./stream";

// Watchlist
export {
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  checkWatchlistStatus,
} from "./watchlist";
export type { WatchlistItem, WatchlistResponse } from "./watchlist";

// Workers & Stats
export { getWorkersStatus, getSystemStats } from "./workers";
export type {
  WorkerInfo,
  WorkersSummary,
  WorkersStatusResponse,
  SystemStats,
} from "./workers";
