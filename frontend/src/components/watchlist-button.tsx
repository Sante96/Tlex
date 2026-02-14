"use client";

import { useEffect, useState } from "react";
import { Heart } from "lucide-react";
import { DSButton } from "@/components/ds";
import {
  addToWatchlist,
  removeFromWatchlist,
  checkWatchlistStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface WatchlistButtonProps {
  mediaId: number;
  className?: string;
}

export function WatchlistButton({ mediaId, className }: WatchlistButtonProps) {
  const [inWatchlist, setInWatchlist] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const status = await checkWatchlistStatus(mediaId);
        setInWatchlist(status);
      } catch {
        // Failed to check watchlist status
      } finally {
        setLoading(false);
      }
    };
    checkStatus();
  }, [mediaId]);

  const handleToggle = async () => {
    try {
      setLoading(true);
      if (inWatchlist) {
        await removeFromWatchlist(mediaId);
        setInWatchlist(false);
      } else {
        await addToWatchlist(mediaId);
        setInWatchlist(true);
      }
    } catch {
      // Failed to toggle watchlist
    } finally {
      setLoading(false);
    }
  };

  return (
    <DSButton
      variant="ghost"
      onClick={handleToggle}
      disabled={loading}
      className={cn("!px-2 !h-10 !w-10", className)}
      title={inWatchlist ? "Rimuovi dalla lista" : "Aggiungi alla lista"}
      icon={
        <Heart
          className={cn(
            "h-5 w-5 transition-colors",
            inWatchlist && "fill-red-500 text-red-500",
          )}
        />
      }
    />
  );
}
