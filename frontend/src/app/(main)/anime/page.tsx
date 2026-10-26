"use client";

import { useTranslations } from "next-intl";
import { PosterCard } from "@/components/ds";
import { LibraryPage } from "@/components/layout/library-page";
import { getAnimeList, type AnimeItem } from "@/lib/api";
import { getTmdbImageUrl, yearOf } from "@/lib/format";

const loadAnime = (page: number, size: number) =>
  getAnimeList({ page, page_size: size, sort: "title" });

/** Japanese animation: series and films together (TMDB says which, an admin can say otherwise) */
export default function AnimePage() {
  const t = useTranslations();
  return (
    <LibraryPage<AnimeItem>
      title={t("nav.anime")}
      emptyText={t("media.animeEmpty")}
      load={loadAnime}
      renderItem={(a) => (
        <PosterCard
          key={`${a.kind}-${a.id}`}
          href={a.kind === "series" ? `/series/${a.id}` : `/media/${a.id}`}
          imageUrl={getTmdbImageUrl(a.poster_path, "w300")}
          title={a.title}
          subtitle={
            a.kind === "movie"
              ? [t("media.movieLabel"), a.date ? yearOf(a.date) : null].filter(Boolean).join(" · ")
              : a.seasons_count === 1
                ? `1 ${t("media.season")}`
                : `${a.seasons_count ?? 0} ${t("media.seasons")}`
          }
        />
      )}
    />
  );
}
