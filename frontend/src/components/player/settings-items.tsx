import { Check, ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { Slider } from "@/components/ui/slider";

const FRAME_DURATION = 1 / 24;

function secondsToFrames(seconds: number): number {
  return Math.round(seconds / FRAME_DURATION);
}

function framesToSeconds(frames: number): number {
  return frames * FRAME_DURATION;
}

export function SyncSubmenu({
  subtitleOffset,
  onSubtitleOffsetChange,
  onBack,
}: {
  subtitleOffset: number;
  onSubtitleOffsetChange: (offset: number) => void;
  onBack: () => void;
}) {
  return (
    <>
      <SubMenuHeader label="Sync sottotitoli" onBack={onBack} />
      <div className="px-4 py-3 space-y-3">
        <div className="flex items-center justify-between">
          <input
            type="number"
            value={secondsToFrames(subtitleOffset)}
            onChange={(e) => {
              const frames = parseInt(e.target.value, 10);
              if (!isNaN(frames))
                onSubtitleOffsetChange(framesToSeconds(frames));
            }}
            className={cn(
              "w-20 text-sm font-mono bg-white/5 border border-white/10 rounded-lg px-2 py-1.5 text-center outline-none focus:border-plex-orange/50",
              subtitleOffset === 0 ? "text-zinc-400" : "text-plex-orange",
            )}
            step="1"
          />
          <span className="text-xs text-zinc-500">frame</span>
          {subtitleOffset !== 0 && (
            <button
              onClick={() => onSubtitleOffsetChange(0)}
              className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
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
        <div className="flex justify-between text-[10px] text-zinc-500">
          <span>-20s (← Prima)</span>
          <span>(Dopo →) +20s</span>
        </div>
      </div>
    </>
  );
}

export function SubMenuHeader({
  label,
  onBack,
}: {
  label: string;
  onBack: () => void;
}) {
  return (
    <div className="border-b border-white/[0.06] mb-1.5">
      <button
        onClick={onBack}
        className="flex items-center w-full px-4 h-[44px] text-[13px] text-white hover:bg-white/[0.08] transition-colors"
      >
        <ChevronLeft className="h-5 w-5 mr-3 text-zinc-400" />
        {label}
      </button>
    </div>
  );
}

export function MenuItem({
  icon,
  label,
  value,
  onClick,
  hasSubmenu,
}: {
  icon: React.ReactNode;
  label: string;
  value?: string;
  onClick: () => void;
  hasSubmenu?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center mx-2 px-3 h-11 text-[13px] text-white hover:bg-white/[0.08] rounded-lg transition-colors"
      style={{ width: "calc(100% - 16px)" }}
    >
      <span className="text-white/70 mr-4 flex-shrink-0">{icon}</span>
      <span className="flex-1 text-left">{label}</span>
      <span className="text-[13px] text-white/70 flex-shrink-0">{value}</span>
      {hasSubmenu && (
        <ChevronRight className="h-4 w-4 text-white/40 ml-0.5 flex-shrink-0" />
      )}
    </button>
  );
}

export function SelectItem({
  label,
  detail,
  selected,
  onClick,
}: {
  label: string;
  detail?: string | null;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center mx-2 px-3 h-11 text-[13px] rounded-lg transition-colors hover:bg-white/[0.08]",
        selected ? "text-plex-orange bg-plex-orange/10" : "text-white",
      )}
      style={{ width: "calc(100% - 16px)" }}
    >
      <span className="w-5 flex-shrink-0 flex justify-center mr-4">
        {selected && <Check className="h-4 w-4" />}
      </span>
      <span className="flex-1 text-left truncate">
        {label}
        {detail && (
          <span className="text-zinc-500 ml-2 text-[12px]">{detail}</span>
        )}
      </span>
    </button>
  );
}
