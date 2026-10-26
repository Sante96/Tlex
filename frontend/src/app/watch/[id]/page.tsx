"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { isAxiosError } from "axios";
import { ArrowLeft, Play, RotateCcw } from "lucide-react";
import { ActionButton, DSButton, DSIconButton } from "@/components/ds";
import { VideoPlayer } from "@/components/player";
import {
  getMediaDetails,
  getWatchProgress,
  type MediaDetails,
} from "@/lib/api";
import { cleanEpisodeTitle, formatTime, getTmdbImageUrl } from "@/lib/format";
import { useProfile } from "@/contexts/profile-context";
import { AuthGuard } from "@/components/auth-guard";

// The player lives outside the (main) layout and its AuthGuard
export default function WatchPage() {
  return (
    <AuthGuard>
      <Watch />
    </AuthGuard>
  );
}

function Watch() {
  const params = useParams();
  const router = useRouter();
  const t = useTranslations();
  const mediaId = Number(params.id);
  // The player picks audio and subtitles from the profile's Settings: wait for it, or a
  // late profile would switch the audio track (and restart the stream) right after start
  const { isLoading: profileLoading } = useProfile();

  const [media, setMedia] = useState<MediaDetails | null>(null);
  const [initialPosition, setInitialPosition] = useState(0);
  // Taken out of Continue Watching: where it was, until the viewer picks resume or start over
  const [askFrom, setAskFrom] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mediaId || isNaN(mediaId)) {
      setError(t("media.notFound"));
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
        if (progress && !progress.completed && progress.position_seconds > 0) {
          if (progress.hidden) setAskFrom(progress.position_seconds);
          else setInitialPosition(progress.position_seconds);
        }
      } catch (e) {
        setError(
          isAxiosError(e) && e.response?.status === 404
            ? t("media.notFound")
            : t("common.loadError"),
        );
      } finally {
        setLoading(false);
      }
    };

    loadMedia();
  }, [mediaId, t]);

  // The player releases the old stream when it unmounts (this page shows a loader
  // while the next episode loads)
  const handleEpisodeSelect = useCallback(
    (newMediaId: number) => {
      router.replace(`/watch/${newMediaId}`);
    },
    [router],
  );

  const audioTracks =
    media?.streams.filter((s) => s.codec_type === "AUDIO") || [];

  const subtitleTracks =
    media?.streams.filter((s) => s.codec_type === "SUBTITLE") || [];

  if (loading || profileLoading) {
    return (
      <div className="fixed inset-0 bg-black flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-white"></div>
      </div>
    );
  }

  if (error || !media) {
    return (
      <div className="fixed inset-0 bg-black flex flex-col items-center justify-center gap-4">
        <p className="text-white text-xl">{error || t("media.notFound")}</p>
        <DSButton
          variant="secondary"
          onClick={() => router.push("/")}
          icon={<ArrowLeft className="h-4 w-4" />}
        >
          {t("nav.home")}
        </DSButton>
      </div>
    );
  }

  const isEpisode = media.media_type === "EPISODE";
  const isConcert = media.media_type === "CONCERT";
  const title = isEpisode ? cleanEpisodeTitle(media.title) : media.title;
  // A concert's songs: the setlist's titles over the file's (lines past the last
  // chapter have nothing to name)
  const chapters = isConcert
    ? media.chapters?.map((c, i) => ({ ...c, title: media.setlist?.[i] || c.title }))
    : media.chapters;

  const episodeSubtitle = isEpisode
    ? `S${media.season_number || 1} · E${media.episode_number || 1}`
    : undefined;
  const subtitle = isConcert ? (media.franchise_title ?? undefined) : episodeSubtitle;

  if (askFrom !== null) {
    const backdrop = getTmdbImageUrl(media.backdrop_path, "w1280");
    const start = (position: number) => {
      setInitialPosition(position);
      setAskFrom(null);
    };
    return (
      <div className="fixed inset-0 bg-black flex items-center justify-center px-6">
        {backdrop && (
          // eslint-disable-next-line @next/next/no-img-element -- a dimmed backdrop, any size
          <img src={backdrop} alt="" className="absolute inset-0 size-full object-cover opacity-25" />
        )}
        <DSIconButton
          icon={<ArrowLeft className="h-5 w-5" />}
          aria-label={t("common.back")}
          onClick={() => router.back()}
          className="absolute top-4 left-4 h-10 w-10 text-white"
        />
        <div className="relative flex flex-col items-center gap-6 text-center text-shadow">
          <div className="flex flex-col gap-1">
            {subtitle && <p className="text-sm text-white/70">{subtitle}</p>}
            <h1 className="text-2xl md:text-4xl font-bold text-white">{title}</h1>
          </div>
          <div className="flex flex-col sm:flex-row gap-3">
            <ActionButton autoFocus icon={<Play className="h-5 w-5 fill-current" />} onClick={() => start(askFrom)}>
              {t("player.resumeFrom", { time: formatTime(askFrom) })}
            </ActionButton>
            <ActionButton variant="secondary" icon={<RotateCcw className="h-5 w-5" />} onClick={() => start(0)}>
              {t("player.startOver")}
            </ActionButton>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black">
      <VideoPlayer
        mediaId={mediaId}
        title={title}
        subtitle={subtitle}
        audioTracks={audioTracks}
        subtitleTracks={subtitleTracks}
        initialDuration={media.duration_seconds || undefined}
        initialPosition={initialPosition}
        chapters={chapters}
        chapterWord={isConcert ? "song" : "chapter"}
        seriesId={isEpisode ? media.series_id : undefined}
        isMovie={media.media_type === "MOVIE"}
        creditsStart={media.credits_start}
        creditsOwn={media.credits_start_seconds}
        currentSeason={media.season_number || 1}
        onEpisodeSelect={isEpisode ? handleEpisodeSelect : undefined}
      />
    </div>
  );
}
