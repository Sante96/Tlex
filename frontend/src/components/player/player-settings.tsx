"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Volume2, Subtitles, Clock } from "lucide-react";
import { AnimatedSettings } from "./animated-icons";
import { cn } from "@/lib/utils";
import type { MediaStream } from "@/lib/api";
import {
  SubMenuHeader,
  MenuItem,
  SelectItem,
  SyncSubmenu,
} from "./settings-items";

interface PlayerSettingsProps {
  audioTracks: MediaStream[];
  subtitleTracks: MediaStream[];
  selectedAudio: number;
  selectedSubtitle: number | null;
  subtitleOffset: number;
  onAudioChange: (index: number) => void;
  onSubtitleChange: (index: number | null) => void;
  onSubtitleOffsetChange: (offset: number) => void;
  onOpenChange?: (open: boolean) => void;
}

type MenuView = "main" | "audio" | "subtitle" | "sync";

const FRAME_DURATION = 1 / 24;
function secondsToFrames(s: number): number {
  return Math.round(s / FRAME_DURATION);
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
  onOpenChange,
}: PlayerSettingsProps) {
  const [view, setView] = useState<MenuView>("main");
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const [menuHeight, setMenuHeight] = useState<number | "auto">("auto");
  const [menuWidth, setMenuWidth] = useState<number | "auto">("auto");
  const mainRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLDivElement>(null);
  const subtitleRef = useRef<HTMLDivElement>(null);
  const syncRef = useRef<HTMLDivElement>(null);

  const toggle = useCallback(() => {
    const next = !open;
    setOpen(next);
    onOpenChange?.(next);
    if (!next) {
      setTimeout(() => setView("main"), 200); // Wait for close animation before resetting view
    }
  }, [open, onOpenChange]);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        panelRef.current?.contains(target) ||
        buttonRef.current?.contains(target)
      )
        return;
      setOpen(false);
      onOpenChange?.(false);
      setTimeout(() => setView("main"), 200);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, onOpenChange]);

  // Update menu height and width based on active view
  useEffect(() => {
    if (!open) return;
    const activeRef =
      view === "main"
        ? mainRef
        : view === "audio"
          ? audioRef
          : view === "subtitle"
            ? subtitleRef
            : syncRef;

    if (activeRef.current) {
      setMenuHeight(activeRef.current.offsetHeight);
      // We set width explicitly so it can animate, with a minimum of 280px
      setMenuWidth(Math.max(280, activeRef.current.offsetWidth));
    }
  }, [view, open, audioTracks, subtitleTracks]);

  const goBack = () => setView("main");

  const selectedAudioLabel =
    audioTracks[selectedAudio]?.language || `Traccia ${selectedAudio + 1}`;

  const selectedSubLabel =
    selectedSubtitle !== null
      ? subtitleTracks.find((t) => t.stream_index === selectedSubtitle)
          ?.language || "On"
      : "Off";

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={toggle}
        className={cn(
          "p-2 rounded-full transition-colors",
          open ? "bg-white/10" : "hover:bg-white/10",
        )}
      >
        <AnimatedSettings isOpen={open} className="text-white" />
      </button>

      {open && (
        <div
          ref={panelRef}
          className="absolute bottom-full right-0 mb-3 backdrop-blur-xs rounded-xl shadow-[0_8px_32px_rgba(0,0,0,0.5)] overflow-hidden transition-[height,width] duration-200 ease-out"
          style={{
            backgroundColor: "rgba(10, 10, 10, 0.6)",
            height: menuHeight === "auto" ? "auto" : `${menuHeight}px`,
            width: menuWidth === "auto" ? "auto" : `${menuWidth}px`,
          }}
        >
          {/* Sliding container */}
          <div
            className="relative h-full"
            style={{ width: menuWidth === "auto" ? "max-content" : "100%" }}
          >
            {/* Main menu */}
            <div
              ref={mainRef}
              className={cn(
                "min-w-[280px] w-max transition-all duration-200 ease-out",
                view === "main"
                  ? "translate-x-0 opacity-100 relative"
                  : "-translate-x-full opacity-0 absolute top-0 left-0",
              )}
            >
              <div className="py-1.5">
                {/* Audio */}
                {audioTracks.length > 0 && (
                  <MenuItem
                    icon={<Volume2 className="h-5 w-5" />}
                    label="Audio"
                    value={selectedAudioLabel}
                    onClick={() => setView("audio")}
                    hasSubmenu
                  />
                )}

                {/* Subtitles */}
                <MenuItem
                  icon={<Subtitles className="h-5 w-5" />}
                  label="Sottotitoli"
                  value={selectedSubLabel}
                  onClick={() => setView("subtitle")}
                  hasSubmenu
                />

                {/* Subtitle Sync */}
                {selectedSubtitle !== null && (
                  <MenuItem
                    icon={<Clock className="h-5 w-5" />}
                    label="Sync sottotitoli"
                    value={
                      subtitleOffset === 0
                        ? "0"
                        : `${secondsToFrames(subtitleOffset)} frame`
                    }
                    onClick={() => setView("sync")}
                    hasSubmenu
                  />
                )}
              </div>
            </div>

            {/* Audio submenu */}
            <div
              ref={audioRef}
              className={cn(
                "min-w-[280px] w-max transition-all duration-200 ease-out",
                view === "audio"
                  ? "translate-x-0 opacity-100 relative"
                  : "translate-x-full opacity-0 absolute top-0 left-0",
              )}
            >
              <SubMenuHeader label="Audio" onBack={goBack} />
              <div className="py-2 max-h-[320px] overflow-y-auto">
                {audioTracks.map((track, idx) => (
                  <SelectItem
                    key={track.id}
                    label={track.language || `Traccia ${idx + 1}`}
                    detail={track.title}
                    selected={selectedAudio === idx}
                    onClick={() => {
                      onAudioChange(idx);
                      goBack();
                    }}
                  />
                ))}
              </div>
            </div>

            {/* Subtitle submenu */}
            <div
              ref={subtitleRef}
              className={cn(
                "min-w-[280px] w-max transition-all duration-200 ease-out",
                view === "subtitle"
                  ? "translate-x-0 opacity-100 relative"
                  : "translate-x-full opacity-0 absolute top-0 left-0",
              )}
            >
              <SubMenuHeader label="Sottotitoli" onBack={goBack} />
              <div className="py-2 max-h-[320px] overflow-y-auto">
                <SelectItem
                  label="Disattivati"
                  selected={selectedSubtitle === null}
                  onClick={() => {
                    onSubtitleChange(null);
                    goBack();
                  }}
                />
                {subtitleTracks.map((track, idx) => (
                  <SelectItem
                    key={track.id}
                    label={track.language || `Traccia ${idx + 1}`}
                    detail={track.title}
                    selected={selectedSubtitle === track.stream_index}
                    onClick={() => {
                      onSubtitleChange(track.stream_index);
                      goBack();
                    }}
                  />
                ))}
              </div>
            </div>

            {/* Sync submenu */}
            <div
              ref={syncRef}
              className={cn(
                "min-w-[280px] w-max transition-all duration-200 ease-out",
                view === "sync"
                  ? "translate-x-0 opacity-100 relative"
                  : "translate-x-full opacity-0 absolute top-0 left-0",
              )}
            >
              <SyncSubmenu
                subtitleOffset={subtitleOffset}
                onSubtitleOffsetChange={onSubtitleOffsetChange}
                onBack={goBack}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
