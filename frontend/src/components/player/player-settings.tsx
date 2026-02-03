"use client";

import { useState } from "react";
import {
  Check,
  Volume2,
  Subtitles,
  Clock,
  RotateCcw,
  Settings,
  ChevronLeft,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { MediaStream } from "@/lib/api";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Slider } from "@/components/ui/slider";

interface PlayerSettingsProps {
  audioTracks: MediaStream[];
  subtitleTracks: MediaStream[];
  selectedAudio: number;
  selectedSubtitle: number | null;
  subtitleOffset: number;
  onAudioChange: (index: number) => void;
  onSubtitleChange: (index: number | null) => void;
  onSubtitleOffsetChange: (offset: number) => void;
}

const FRAME_DURATION = 1 / 24; // ~0.042s per frame at 24fps

type MenuView = "main" | "audio" | "subtitle";

// Convert seconds to frames
function secondsToFrames(seconds: number): number {
  return Math.round(seconds / FRAME_DURATION);
}

// Convert frames to seconds
function framesToSeconds(frames: number): number {
  return frames * FRAME_DURATION;
}

export function PlayerSettingsDropdown({
  audioTracks,
  subtitleTracks,
  selectedAudio,
  selectedSubtitle,
  subtitleOffset,
  onAudioChange,
  onSubtitleChange,
  onSubtitleOffsetChange,
}: PlayerSettingsProps) {
  const [view, setView] = useState<MenuView>("main");
  const [open, setOpen] = useState(false);

  const handleOpenChange = (isOpen: boolean) => {
    setOpen(isOpen);
    if (!isOpen) setView("main");
  };

  return (
    <DropdownMenu open={open} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <button className="p-2 hover:bg-white/20 rounded-full transition-colors">
          <Settings className="h-5 w-5 text-white" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        side="top"
        sideOffset={12}
        className="w-72 bg-zinc-900/98 backdrop-blur-md border-zinc-700/50 shadow-2xl rounded-lg"
      >
        {view === "main" && (
          <>
            {/* Audio */}
            {audioTracks.length > 0 && (
              <DropdownMenuItem
                onSelect={(e) => {
                  e.preventDefault();
                  setView("audio");
                }}
                className="text-white hover:!bg-plex-orange/25 focus:!bg-plex-orange/25 cursor-pointer justify-between py-3 px-3 rounded-md mx-1 transition-colors duration-150"
              >
                <span className="flex items-center">
                  <Volume2 className="h-4 w-4 mr-3 text-plex-orange" />
                  Audio
                </span>
                <span className="text-xs text-zinc-400 uppercase tracking-wide">
                  {audioTracks[selectedAudio]?.language ||
                    `Traccia ${selectedAudio + 1}`}
                </span>
              </DropdownMenuItem>
            )}

            {/* Subtitles */}
            <DropdownMenuItem
              onSelect={(e) => {
                e.preventDefault();
                setView("subtitle");
              }}
              className="text-white hover:!bg-plex-orange/25 focus:!bg-plex-orange/25 cursor-pointer justify-between py-3 px-3 rounded-md mx-1 transition-colors duration-150"
            >
              <span className="flex items-center">
                <Subtitles className="h-4 w-4 mr-3 text-plex-orange" />
                Sottotitoli
              </span>
              <span className="text-xs text-zinc-400 uppercase tracking-wide">
                {selectedSubtitle !== null
                  ? subtitleTracks.find(
                      (t) => t.stream_index === selectedSubtitle,
                    )?.language || "On"
                  : "Off"}
              </span>
            </DropdownMenuItem>

            {/* Subtitle Sync - only show when subtitles are active */}
            {selectedSubtitle !== null && (
              <>
                <DropdownMenuSeparator className="bg-zinc-700" />
                <DropdownMenuLabel className="text-zinc-400 flex items-center gap-2 text-xs">
                  <Clock className="h-3.5 w-3.5" />
                  Sync Sottotitoli
                </DropdownMenuLabel>
                <div className="px-2 py-2">
                  <div className="flex items-center justify-between mb-2">
                    <input
                      type="number"
                      value={secondsToFrames(subtitleOffset)}
                      onChange={(e) => {
                        const frames = parseInt(e.target.value, 10);
                        if (!isNaN(frames))
                          onSubtitleOffsetChange(framesToSeconds(frames));
                      }}
                      className={cn(
                        "w-20 text-sm font-mono bg-transparent border border-zinc-600 rounded px-1 py-0.5 text-center",
                        subtitleOffset === 0
                          ? "text-zinc-400"
                          : "text-plex-orange",
                      )}
                      step="1"
                    />
                    <span className="text-xs text-zinc-500">frame</span>
                    {subtitleOffset !== 0 && (
                      <button
                        onClick={() => onSubtitleOffsetChange(0)}
                        className="p-1 hover:bg-white/10 rounded transition-colors"
                        title="Reset"
                      >
                        <RotateCcw className="h-3.5 w-3.5 text-zinc-400" />
                      </button>
                    )}
                  </div>
                  <Slider
                    value={[secondsToFrames(subtitleOffset)]}
                    onValueChange={([frames]) =>
                      onSubtitleOffsetChange(framesToSeconds(frames))
                    }
                    min={-480}
                    max={480}
                    step={1}
                    className="w-full"
                  />
                  <div className="flex justify-between mt-1 text-[10px] text-zinc-500">
                    <span>-20s (← Prima)</span>
                    <span>(Dopo →) +20s</span>
                  </div>
                </div>
              </>
            )}
          </>
        )}

        {view === "audio" && (
          <>
            <DropdownMenuItem
              onSelect={(e) => {
                e.preventDefault();
                setView("main");
              }}
              className="text-zinc-400 hover:bg-white/10 hover:text-white focus:bg-white/10 cursor-pointer transition-all duration-150 py-2"
            >
              <ChevronLeft className="h-4 w-4 mr-2" />
              Audio
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-zinc-700" />
            {audioTracks.map((track, idx) => (
              <DropdownMenuItem
                key={track.id}
                onClick={() => {
                  onAudioChange(idx);
                  setView("main");
                }}
                className={cn(
                  "text-white hover:!bg-plex-orange/25 focus:!bg-plex-orange/25 cursor-pointer transition-colors duration-150 py-2.5 rounded-md mx-1",
                  selectedAudio === idx &&
                    "text-plex-orange !bg-plex-orange/15",
                )}
              >
                {selectedAudio === idx && <Check className="h-4 w-4 mr-2" />}
                <span className={selectedAudio !== idx ? "ml-6" : ""}>
                  {track.language || `Traccia ${idx + 1}`}
                  {track.title && ` - ${track.title}`}
                </span>
              </DropdownMenuItem>
            ))}
          </>
        )}

        {view === "subtitle" && (
          <>
            <DropdownMenuItem
              onSelect={(e) => {
                e.preventDefault();
                setView("main");
              }}
              className="text-zinc-400 hover:bg-white/10 hover:text-white focus:bg-white/10 cursor-pointer transition-all duration-150 py-2"
            >
              <ChevronLeft className="h-4 w-4 mr-2" />
              Sottotitoli
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-zinc-700" />
            <DropdownMenuItem
              onClick={() => {
                onSubtitleChange(null);
                setView("main");
              }}
              className={cn(
                "text-white hover:!bg-plex-orange/25 focus:!bg-plex-orange/25 cursor-pointer transition-colors duration-150 py-2.5 rounded-md mx-1",
                selectedSubtitle === null &&
                  "text-plex-orange !bg-plex-orange/15",
              )}
            >
              {selectedSubtitle === null && <Check className="h-4 w-4 mr-2" />}
              <span className={selectedSubtitle !== null ? "ml-6" : ""}>
                Disattivati
              </span>
            </DropdownMenuItem>
            {subtitleTracks.map((track, idx) => (
              <DropdownMenuItem
                key={track.id}
                onClick={() => {
                  onSubtitleChange(track.stream_index);
                  setView("main");
                }}
                className={cn(
                  "text-white hover:!bg-plex-orange/25 focus:!bg-plex-orange/25 cursor-pointer transition-colors duration-150 py-2.5 rounded-md mx-1",
                  selectedSubtitle === track.stream_index &&
                    "text-plex-orange !bg-plex-orange/15",
                )}
              >
                {selectedSubtitle === track.stream_index && (
                  <Check className="h-4 w-4 mr-2" />
                )}
                <span
                  className={
                    selectedSubtitle !== track.stream_index ? "ml-6" : ""
                  }
                >
                  {track.language || `Traccia ${idx + 1}`}
                  {track.title && ` - ${track.title}`}
                </span>
              </DropdownMenuItem>
            ))}
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
