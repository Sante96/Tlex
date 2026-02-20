// Re-export everything from modules
export { api, API_BASE_URL } from "./client";

// Auth
export {
  login,
  register,
  getCurrentUser,
  changePassword,
  getRegistrationStatus,
  setRegistrationStatus,
} from "./auth";
export type { LoginResponse, UserResponse, UserInfo } from "./auth";
export { listUsers, toggleUserAdmin, deleteUser } from "./auth";

// Media
export {
  getMediaList,
  getMediaDetails,
  deleteMedia,
  refreshMetadata,
  getMediaCast,
  getMediaEpisodes,
  getNextEpisode,
  updateMediaItem,
  getMediaTmdbImages,
  triggerScan,
  getScanStatus,
} from "./media";
export type {
  MediaItem,
  MediaStream,
  MediaDetails,
  CastMember,
  EpisodeInfo,
  NextEpisode,
  TMDBImage,
  TMDBImagesResponse,
  MediaUpdateBody,
} from "./media";

// Series
export {
  getSeriesList,
  getSeriesDetails,
  refreshSeriesMetadata,
  getSeriesCast,
  updateSeries,
  getSeriesTmdbImages,
  updateSeasonPoster,
  getSeasonTmdbImages,
} from "./series";
export type {
  SeriesItem,
  SeasonInfo,
  SeriesDetails,
  EpisodeWatchProgress,
  SeriesUpdateBody,
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
  releaseStream,
  getPoolStatus,
} from "./stream";
export type { PoolStatus } from "./stream";

// Watchlist
export {
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  checkWatchlistStatus,
  addSeriesToWatchlist,
  removeSeriesFromWatchlist,
  checkSeriesWatchlistStatus,
} from "./watchlist";
export type { WatchlistItem, WatchlistResponse } from "./watchlist";

// Workers & Stats
export {
  getWorkersStatus,
  getSystemStats,
  sendWorkerCode,
  verifyWorkerCode,
  deleteWorker,
} from "./workers";
export type {
  WorkerInfo,
  WorkersSummary,
  WorkersStatusResponse,
  SystemStats,
} from "./workers";

// Scanner
export {
  getAutoScanStatus,
  getScanStatus as getScannerStatus,
  triggerScan as triggerManualScan,
  setAutoScanInterval,
} from "./scanner";
export type { AutoScanStatus, ScanStatus } from "./scanner";
