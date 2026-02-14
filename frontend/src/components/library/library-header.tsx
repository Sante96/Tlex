"use client";

import { RefreshCw, Grid3X3, List } from "lucide-react";
import { DSButton } from "@/components/ds";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface LibraryHeaderProps {
  title: string;
  totalCount: number;
  sortBy?: string;
  onSortChange?: (value: string) => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function LibraryHeader({
  title,
  totalCount,
  sortBy = "title",
  onSortChange,
  onRefresh,
  isRefreshing,
}: LibraryHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold text-white">{title}</h1>
        <p className="text-sm text-muted-foreground">{totalCount} elementi</p>
      </div>

      <div className="flex items-center gap-3">
        {/* Sort */}
        <Select value={sortBy} onValueChange={onSortChange}>
          <SelectTrigger className="w-[160px] bg-zinc-800 border-zinc-700">
            <SelectValue placeholder="Ordina per" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="title">Titolo</SelectItem>
            <SelectItem value="date_added">Data aggiunta</SelectItem>
            <SelectItem value="release_date">Data uscita</SelectItem>
          </SelectContent>
        </Select>

        {/* View toggle */}
        <div className="flex border border-zinc-700 rounded-md overflow-hidden">
          <DSButton
            variant="ghost"
            className="!rounded-none bg-zinc-800 !px-2 !h-9"
            icon={<Grid3X3 className="h-4 w-4" />}
          />
          <DSButton
            variant="ghost"
            className="!rounded-none !px-2 !h-9"
            icon={<List className="h-4 w-4" />}
          />
        </div>

        {/* Refresh */}
        {onRefresh && (
          <DSButton
            variant="secondary"
            onClick={onRefresh}
            disabled={isRefreshing}
            icon={
              <RefreshCw
                className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`}
              />
            }
          >
            Aggiorna
          </DSButton>
        )}
      </div>
    </div>
  );
}
