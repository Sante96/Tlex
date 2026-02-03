"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { VideoPlayer } from "@/components/player";
import {
  getMediaDetails,
  getWatchProgress,
  type MediaDetails,
} from "@/lib/api";

export default function WatchPage() {
  const params = useParams();
  const router = useRouter();
  const mediaId = Number(params.id);

  const [media, setMedia] = useState<MediaDetails | null>(null);
  const [initialPosition, setInitialPosition] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mediaId || isNaN(mediaId)) {
      setError("Invalid media ID");
      setLoading(false);
      return;
    }

    const loadMedia = async () => {
      try {
        setLoading(true);
        const [data, progress] = await Promise.all([
          getMediaDetails(mediaId),
          getWatchProgress(mediaId),
        ]);
        setMedia(data);
        // Resume from saved position if available and not completed
        if (progress && !progress.completed && progress.position_seconds > 0) {
          setInitialPosition(progress.position_seconds);
        }
      } catch (err) {
        console.error("Failed to load media:", err);
        setError("Failed to load media");
      } finally {
        setLoading(false);
      }
    };

    loadMedia();
  }, [mediaId]);

  const audioTracks =
    media?.streams.filter((s) => s.codec_type === "AUDIO") || [];

  const subtitleTracks =
    media?.streams.filter((s) => s.codec_type === "SUBTITLE") || [];

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-white"></div>
      </div>
    );
  }

  if (error || !media) {
    return (
      <div className="fixed inset-0 bg-black flex flex-col items-center justify-center gap-4">
        <p className="text-white text-xl">{error || "Media not found"}</p>
        <Button variant="outline" onClick={() => router.push("/")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Home
        </Button>
      </div>
    );
  }

  const episodeSubtitle =
    media.media_type === "EPISODE"
      ? `S${media.season_number || 1} · E${media.episode_number || 1}`
      : undefined;

  return (
    <div className="fixed inset-0 bg-black">
      <VideoPlayer
        mediaId={mediaId}
        title={media.title}
        subtitle={episodeSubtitle}
        audioTracks={audioTracks}
        subtitleTracks={subtitleTracks}
        initialDuration={media.duration_seconds || undefined}
        initialPosition={initialPosition}
      />
    </div>
  );
}
