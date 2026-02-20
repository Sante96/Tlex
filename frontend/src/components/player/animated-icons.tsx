"use client";

import { motion } from "framer-motion";

const transition = { duration: 0.2, ease: [0.4, 0, 0.2, 1] as const };

// Play/Pause: two quadrilaterals that morph between a triangle (play) and two bars (pause)
const PLAY_PATH =
  "M 8 5 L 8 19 L 13 16 L 13 8 Z M 13 8 L 13 16 L 19 12 L 19 12 Z";
const PAUSE_PATH =
  "M 8 5 L 8 19 L 12 19 L 12 5 Z M 14 5 L 14 19 L 18 19 L 18 5 Z";

interface AnimatedPlayPauseProps {
  isPlaying: boolean;
  className?: string;
  size?: number;
}

export function AnimatedPlayPause({
  isPlaying,
  className,
  size = 24,
}: AnimatedPlayPauseProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      fill="currentColor"
    >
      <motion.path
        d={isPlaying ? PAUSE_PATH : PLAY_PATH}
        animate={{ d: isPlaying ? PAUSE_PATH : PLAY_PATH }}
        transition={transition}
        fill="currentColor"
      />
    </svg>
  );
}

// Volume icon
const SPEAKER_PATH = "M 3 9 L 3 15 L 7 15 L 12 19 L 12 5 L 7 9 Z";
const WAVE_SMALL =
  "M 14.5 9.5 C 15.3 10.2 15.8 11.1 15.8 12 C 15.8 12.9 15.3 13.8 14.5 14.5";
const WAVE_BIG =
  "M 14.5 6.5 C 16.5 8.0 17.8 9.9 17.8 12 C 17.8 14.1 16.5 16.0 14.5 17.5";
const MUTE_X = "M 16 9 L 20 13 M 20 9 L 16 13";

interface AnimatedVolumeProps {
  volume: number;
  isMuted: boolean;
  className?: string;
  size?: number;
}

export function AnimatedVolume({
  volume,
  isMuted,
  className,
  size = 24,
}: AnimatedVolumeProps) {
  const showSmallWave = !isMuted && volume > 0;
  const showBigWave = !isMuted && volume >= 0.5;
  const showMute = isMuted || volume === 0;

  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={SPEAKER_PATH} fill="currentColor" stroke="none" />
      <motion.path
        d={WAVE_SMALL}
        initial={false}
        animate={{
          opacity: showSmallWave ? 1 : 0,
          pathLength: showSmallWave ? 1 : 0,
        }}
        transition={{ duration: 0.15 }}
      />
      <motion.path
        d={WAVE_BIG}
        initial={false}
        animate={{
          opacity: showBigWave ? 1 : 0,
          pathLength: showBigWave ? 1 : 0,
        }}
        transition={{ duration: 0.15, delay: showBigWave ? 0.05 : 0 }}
      />
      <motion.path
        d={MUTE_X}
        initial={false}
        animate={{ opacity: showMute ? 1 : 0, pathLength: showMute ? 1 : 0 }}
        transition={{ duration: 0.15 }}
      />
    </svg>
  );
}

// Settings gear — rotates when open/closed
interface AnimatedSettingsProps {
  isOpen: boolean;
  className?: string;
  size?: number;
}

export function AnimatedSettings({
  isOpen,
  className,
  size = 20,
}: AnimatedSettingsProps) {
  return (
    <motion.svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      animate={{ rotate: isOpen ? 60 : 0 }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] as const }}
    >
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </motion.svg>
  );
}

// Fullscreen: morph between expand and compress
const MAXIMIZE_PATH =
  "M 3 8 L 3 3 L 8 3 M 16 3 L 21 3 L 21 8 M 21 16 L 21 21 L 16 21 M 8 21 L 3 21 L 3 16";
const MINIMIZE_PATH =
  "M 8 3 L 8 8 L 3 8 M 21 8 L 16 8 L 16 3 M 16 21 L 16 16 L 21 16 M 3 16 L 8 16 L 8 21";

interface AnimatedFullscreenProps {
  isFullscreen: boolean;
  className?: string;
  size?: number;
}

export function AnimatedFullscreen({
  isFullscreen,
  className,
  size = 20,
}: AnimatedFullscreenProps) {
  const path = isFullscreen ? MINIMIZE_PATH : MAXIMIZE_PATH;
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <motion.path d={path} animate={{ d: path }} transition={transition} />
    </svg>
  );
}

// Episodes list — morphs between list+play (closed) and list+active (open)
interface AnimatedEpisodesProps {
  isOpen: boolean;
  className?: string;
  size?: number;
}

const LINES_CLOSED = ["M16 6H3", "M12 12H3", "M12 18H3"];
const LINES_OPEN = ["M21 6H3", "M21 12H3", "M21 18H3"];
const PLAY_CLOSED = "M16 12L21 15L16 18Z";
const PLAY_OPEN = "M16 12L16 12L16 12Z"; // collapses to nothing

export function AnimatedEpisodes({
  isOpen,
  className,
  size = 20,
}: AnimatedEpisodesProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {LINES_CLOSED.map((closedD, i) => (
        <motion.path
          key={i}
          initial={false}
          animate={{ d: isOpen ? LINES_OPEN[i] : closedD }}
          transition={{ duration: 0.25, delay: i * 0.04, ease: "easeInOut" }}
        />
      ))}
      <motion.path
        fill="currentColor"
        stroke="none"
        initial={false}
        animate={{
          d: isOpen ? PLAY_OPEN : PLAY_CLOSED,
          opacity: isOpen ? 0 : 1,
        }}
        transition={{ duration: 0.2, ease: "easeInOut" }}
      />
    </svg>
  );
}

// Back arrow — slides left on hover
interface AnimatedBackProps {
  className?: string;
  size?: number;
}

export function AnimatedBack({ className, size = 24 }: AnimatedBackProps) {
  return (
    <motion.svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      whileHover={{ x: -2 }}
      transition={{ duration: 0.15 }}
    >
      <path d="M 15 18 L 9 12 L 15 6" />
    </motion.svg>
  );
}
