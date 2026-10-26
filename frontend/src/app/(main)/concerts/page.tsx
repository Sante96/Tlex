"use client";

import { useTranslations } from "next-intl";
import { PosterCard } from "@/components/ds";
import { LibraryPage } from "@/components/layout/library-page";
import { getFranchises, type FranchiseSummary } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";

const loadFranchises = (page: number, size: number) =>
  getFranchises({ page, page_size: size });

/** The Concerts section: an anime/game per card, by name */
export default function ConcertsPage() {
  const t = useTranslations();
  return (
    <LibraryPage<FranchiseSummary>
      title={t("nav.concerts")}
      emptyText={t("media.concertsEmpty")}
      load={loadFranchises}
      renderItem={(f) => (
        <PosterCard
          key={f.id}
          href={`/concerts/${f.id}`}
          imageUrl={getTmdbImageUrl(f.poster_path, "w300")}
          title={f.title}
          subtitle={t("concerts.count", { n: f.concerts_count })}
        />
      )}
    />
  );
}
