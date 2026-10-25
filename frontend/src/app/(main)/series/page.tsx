"use client";

import { useTranslations } from "next-intl";
import { PosterCard } from "@/components/ds";
import { LibraryPage } from "@/components/layout/library-page";
import { getSeriesList, type SeriesItem } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";

const loadSeries = (page: number, size: number) => getSeriesList({ page, page_size: size });

export default function SeriesPage() {
  const t = useTranslations();
  return (
    <LibraryPage<SeriesItem>
      title={t("nav.series")}
      emptyText={t("media.seriesEmpty")}
      load={loadSeries}
      renderItem={(s) => (
        <PosterCard
          key={s.id}
          href={`/series/${s.id}`}
          imageUrl={getTmdbImageUrl(s.poster_path, "w300")}
          title={s.title}
          subtitle={
            s.seasons_count === 1
              ? `1 ${t("media.season")}`
              : `${s.seasons_count} ${t("media.seasons")}`
          }
        />
      )}
    />
  );
}
