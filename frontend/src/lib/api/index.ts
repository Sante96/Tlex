// Re-export everything from modules
export { api, API_BASE_URL, hasSession, sessionStarted, endSession, errorText } from "./client";

// Auth
export {
  login,
  logout,
  register,
  getCurrentUser,
  changePassword,
  getRegistrationStatus,
  setRegistrationStatus,
} from "./auth";
export type { LoginResponse, UserResponse, UserInfo } from "./auth";
export { listUsers, toggleUserAdmin, deleteUser } from "./auth";
export {
  requestDeviceCode,
  confirmDeviceCode,
  pollDeviceCode,
} from "./auth";
export type { DeviceCodeResponse, DevicePollResponse } from "./auth";

// Media
export {
  getMediaList,
  getMediaDetails,
  refreshMetadata,
  getMediaCast,
  getMediaTrailer,
  getNextEpisode,
  updateMediaItem,
  getMediaTmdbImages,
  triggerScan,
} from "./media";
export type {
  MediaItem,
  MediaStream,
  MediaDetails,
  Chapter,
  CastMember,
  EpisodeInfo,
  NextEpisode,
  TMDBImage,
  TMDBImagesResponse,
  MediaUpdateBody,
} from "./media";

// People
export { getPersonDetails } from "./people";
export type { PersonDetails, PersonWork } from "./people";

// Series
export {
  getSeriesList,
  getSeriesDetails,
  refreshSeriesMetadata,
  getSeriesCast,
  getSeriesTrailer,
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
  saveWatchProgressOnExit,
  getContinueWatching,
} from "./progress";
export type { WatchProgress, ContinueWatchingItem } from "./progress";

// Profiles
export {
  getProfiles,
  createProfile,
  updateProfile,
  deleteProfile,
  assignWorkerToProfile,
} from "./profiles";
export type { Profile, ProfileListResponse } from "./profiles";

// Stream & Subtitles
export {
  getStreamUrl,
  warmStream,
  releaseStream,
  getPoolStatus,
  getStreamClients,
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
  getConfiguredChannels,
} from "./scanner";
export type { AutoScanStatus, ScanStatus } from "./scanner";

// Backup
export {
  listBackupChannels,
  createBackupChannel,
  syncBackupChannel,
  toggleBackupChannel,
  deleteBackupChannel,
  promoteBackupChannel,
  getBackupSyncInterval,
  setBackupSyncInterval,
} from "./backup";
export type { BackupChannel, BackupTopic } from "./backup";
export {
  getFranchises,
  getFranchise,
  updateFranchise,
  getFranchiseTmdbImages,
} from "./franchises";
export type {
  FranchiseSummary,
  FranchiseDetails,
  ConcertInfo,
  FranchiseUpdateBody,
} from "./franchises";
export { uploadImage, imageFromUrl } from "./images";
