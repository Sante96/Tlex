"use client";

import { useState, useRef, useEffect } from "react";
import { Calendar, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface DSDatePickerProps {
  value: string;
  onChange: (v: string) => void;
  className?: string;
  disabled?: boolean;
}

const DAY_LABELS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

function buildCells(year: number, month: number): (number | null)[] {
  const firstDay = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  let startDow = firstDay.getDay() - 1;
  if (startDow < 0) startDow = 6;
  const cells: (number | null)[] = [
    ...Array(startDow).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

function formatDisplay(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

export function DSDatePicker({
  value,
  onChange,
  className,
  disabled,
}: DSDatePickerProps) {
  const [open, setOpen] = useState(false);
  const [viewDate, setViewDate] = useState(() =>
    value ? new Date(value + "T00:00:00") : new Date(),
  );
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const today = new Date();
  const selected = value ? new Date(value + "T00:00:00") : null;
  const cells = buildCells(year, month);

  const monthLabel = new Intl.DateTimeFormat(undefined, {
    month: "long",
    year: "numeric",
  }).format(viewDate);

  const prevMonth = () => setViewDate(new Date(year, month - 1, 1));
  const nextMonth = () => setViewDate(new Date(year, month + 1, 1));

  const selectDay = (day: number) => {
    const d = new Date(year, month, day);
    onChange(d.toISOString().split("T")[0]);
    setOpen(false);
  };

  const isSelected = (day: number) =>
    selected?.getFullYear() === year &&
    selected?.getMonth() === month &&
    selected?.getDate() === day;

  const isToday = (day: number) =>
    today.getFullYear() === year &&
    today.getMonth() === month &&
    today.getDate() === day;

  return (
    <div ref={ref} className={cn("relative", className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen((v) => !v)}
        className={cn(
          "flex items-center gap-2 h-10 w-full rounded-lg bg-[#18181b] border px-3 text-sm text-left transition-colors outline-none",
          open
            ? "border-[#e5a00d] border-2 px-[11px]"
            : "border-[#3f3f46] hover:border-[#52525b]",
          value ? "text-[#fafafa]" : "text-[#52525b]",
          disabled && "opacity-50 cursor-not-allowed",
        )}
      >
        <Calendar className="h-4 w-4 text-[#71717a] shrink-0" />
        <span className="flex-1">{value ? formatDisplay(value) : "—"}</span>
      </button>

      {open && (
        <div className="absolute top-full mt-1.5 z-50 rounded-xl border border-[#3f3f46] bg-[#18181b] p-3 shadow-[0_8px_32px_rgba(0,0,0,0.55)] w-[272px]">
          {/* Month/year nav */}
          <div className="flex items-center justify-between mb-3">
            <button
              type="button"
              onClick={prevMonth}
              className="flex items-center justify-center w-7 h-7 rounded-lg hover:bg-[#27272a] transition-colors text-[#a1a1aa] hover:text-white"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-sm font-semibold text-[#fafafa] capitalize">
              {monthLabel}
            </span>
            <button
              type="button"
              onClick={nextMonth}
              className="flex items-center justify-center w-7 h-7 rounded-lg hover:bg-[#27272a] transition-colors text-[#a1a1aa] hover:text-white"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          {/* Day headers */}
          <div className="grid grid-cols-7 mb-1">
            {DAY_LABELS.map((d) => (
              <div
                key={d}
                className="text-center text-[11px] font-medium text-[#52525b] py-1"
              >
                {d}
              </div>
            ))}
          </div>

          {/* Day cells */}
          <div className="grid grid-cols-7 gap-y-0.5">
            {cells.map((day, i) => {
              if (!day) return <div key={i} />;
              const sel = isSelected(day);
              const tod = isToday(day);
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => selectDay(day)}
                  className={cn(
                    "text-sm h-8 w-8 rounded-lg mx-auto flex items-center justify-center transition-colors",
                    sel && "bg-[#e5a00d] text-black font-semibold",
                    !sel && tod && "ring-1 ring-[#e5a00d] text-[#e5a00d]",
                    !sel &&
                      !tod &&
                      "text-[#a1a1aa] hover:bg-[#27272a] hover:text-white",
                  )}
                >
                  {day}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
