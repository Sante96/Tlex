"use client";

import { useTranslations } from "next-intl";
import { PosterCard } from "@/components/ds";
import { LibraryPage } from "@/components/layout/library-page";
import { getMediaList, type MediaItem } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";

const loadMovies = (page: number, size: number) =>
  getMediaList({ media_type: "MOVIE", skip: (page - 1) * size, limit: size });

export default function MoviesPage() {
  const t = useTranslations();
  return (
    <LibraryPage<MediaItem>
      title={t("nav.movies")}
      emptyText={t("media.moviesEmpty")}
      load={loadMovies}
      renderItem={(m) => (
        <PosterCard
          key={m.id}
          href={`/media/${m.id}`}
          imageUrl={getTmdbImageUrl(m.poster_path, "w300")}
          title={m.title}
          subtitle={m.release_date?.slice(0, 4) ?? ""}
        />
      )}
    />
  );
}
