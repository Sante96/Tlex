"use client";

import { useEffect, useState } from "react";
import { Heart } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  addToWatchlist,
  removeFromWatchlist,
  checkWatchlistStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface WatchlistButtonProps {
  mediaId: number;
  size?: "default" | "icon";
  className?: string;
}

export function WatchlistButton({
  mediaId,
  size = "icon",
  className,
}: WatchlistButtonProps) {
  const [inWatchlist, setInWatchlist] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const status = await checkWatchlistStatus(mediaId);
        setInWatchlist(status);
      } catch (error) {
        console.error("Failed to check watchlist status:", error);
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
    } catch (error) {
      console.error("Failed to toggle watchlist:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      variant="outline"
      size={size}
      onClick={handleToggle}
      disabled={loading}
      className={cn(className)}
      title={inWatchlist ? "Rimuovi dalla lista" : "Aggiungi alla lista"}
    >
      <Heart
        className={cn(
          "h-5 w-5 transition-colors",
          inWatchlist && "fill-red-500 text-red-500",
        )}
      />
    </Button>
  );
}
