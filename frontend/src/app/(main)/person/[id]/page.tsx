"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { ArrowLeft } from "lucide-react";
import { getPersonDetails, type PersonDetails } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";
import { PosterCard } from "@/components/ds";
import { Skeleton } from "@/components/ui/skeleton";
import { useIsTV } from "@/hooks/use-platform";

function InstagramIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.744l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

export default function PersonPage() {
  const t = useTranslations();
  const params = useParams();
  const router = useRouter();
  const personId = Number(params.id);

  const [person, setPerson] = useState<PersonDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [bioExpanded, setBioExpanded] = useState(false);
  const isTV = useIsTV();

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const data = await getPersonDetails(personId);
        setPerson(data);
      } catch {
      } finally {
        setLoading(false);
      }
    };
    if (personId) load();
  }, [personId]);

  if (loading) return <PersonSkeleton />;

  if (!person) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-[#a1a1aa]">{t("person.notFound")}</p>
        <button
          onClick={() => router.back()}
          className="text-[#e5a00d] text-sm mt-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e5a00d] rounded"
        >
          {t("media.goBack")}
        </button>
      </div>
    );
  }

  const profileUrl = person.profile_path
    ? getTmdbImageUrl(person.profile_path, "w500")
    : null;
  const birthday = person.birthday
    ? new Date(person.birthday).toLocaleDateString(undefined, {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : null;
  const bioIsTruncatable = (person.biography?.length ?? 0) > 400;

  return (
    <div className={isTV ? "px-8 py-8" : "px-4 md:px-12 py-6 md:py-10"}>
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-2 text-[#a1a1aa] hover:text-white transition-colors mb-8 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e5a00d] rounded"
      >
        <ArrowLeft className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform" />
        <span className="text-sm">{t("common.back")}</span>
      </button>

      {/* Header: photo + info side by side */}
      <div className="flex flex-col sm:flex-row gap-8 md:gap-12 mb-12">
        {/* Photo */}
        <div className="shrink-0 self-start">
          {profileUrl ? (
            <Image
              src={profileUrl}
              alt={person.name}
              width={180}
              height={270}
              className="w-36 h-auto md:w-48 rounded-2xl object-cover shadow-xl ring-1 ring-white/10"
              unoptimized
            />
          ) : (
            <div className="w-36 md:w-48 aspect-[2/3] rounded-2xl bg-[#27272a] flex items-center justify-center text-[#71717a] text-5xl font-semibold">
              {person.name.charAt(0)}
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex flex-col gap-4 min-w-0 pt-1">
          <h1 className="text-3xl md:text-4xl font-bold text-[#fafafa] leading-tight">
            {person.name}
          </h1>

          {/* Meta info */}
          <div className="flex flex-col gap-1">
            {birthday && (
              <p className="text-sm text-[#71717a]">
                <span className="text-[#a1a1aa]">{t("person.bornOn")}</span>{" "}
                {birthday}
              </p>
            )}
            {person.place_of_birth && (
              <p className="text-sm text-[#71717a]">
                <span className="text-[#a1a1aa]">{t("person.bornIn")}</span>{" "}
                {person.place_of_birth}
              </p>
            )}
          </div>

          {/* Social links — hidden on TV (external browser links) */}
          {!isTV && (person.imdb_id || person.instagram_id || person.twitter_id) && (
            <div className="flex items-center gap-3">
              {person.imdb_id && (
                <a
                  href={`https://www.imdb.com/name/${person.imdb_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#27272a] hover:bg-[#3f3f46] transition-colors text-[#a1a1aa] hover:text-white text-xs font-medium"
                >
                  <span className="font-black text-[#f5c518]">IMDb</span>
                </a>
              )}
              {person.instagram_id && (
                <a
                  href={`https://www.instagram.com/${person.instagram_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#27272a] hover:bg-[#3f3f46] transition-colors text-[#a1a1aa] hover:text-white text-xs font-medium"
                >
                  <InstagramIcon className="h-3.5 w-3.5" />
                  <span>{person.instagram_id}</span>
                </a>
              )}
              {person.twitter_id && (
                <a
                  href={`https://x.com/${person.twitter_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#27272a] hover:bg-[#3f3f46] transition-colors text-[#a1a1aa] hover:text-white text-xs font-medium"
                >
                  <XIcon className="h-3 w-3" />
                  <span>@{person.twitter_id}</span>
                </a>
              )}
            </div>
          )}

          {/* Biography */}
          {person.biography && (
            <div className="flex flex-col gap-2">
              <p
                className={`text-sm text-[#a1a1aa] leading-relaxed max-w-3xl ${!bioExpanded && bioIsTruncatable ? "line-clamp-5" : ""}`}
              >
                {person.biography}
              </p>
              {bioIsTruncatable && (
                <button
                  onClick={() => setBioExpanded((v) => !v)}
                  className="text-xs text-[#e5a00d] hover:underline self-start focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e5a00d] rounded"
                >
                  {bioExpanded ? t("common.readLess") : t("common.readMore")}
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Filmography */}
      {person.works.length > 0 ? (
        <section className="flex flex-col gap-6">
          <h2 className="text-2xl font-semibold text-[#fafafa]">
            {t("person.filmography")}
            <span className="text-[#71717a] text-lg font-normal ml-2">
              ({person.works.filter((w) => w.in_catalog).length}{" "}
              {t("person.inCatalog")})
            </span>
          </h2>
          <div className={isTV
            ? "grid grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-4"
            : "grid grid-cols-3 md:grid-cols-5 lg:grid-cols-7 xl:grid-cols-9 2xl:grid-cols-11 gap-3 md:gap-4"
          }>
            {person.works.map((work) => {
              const year = work.release_date
                ? new Date(work.release_date).getFullYear().toString()
                : "";
              const subtitle = work.character ?? work.job ?? year;
              const imageUrl = getTmdbImageUrl(work.poster_path, "w300");

              if (work.in_catalog && work.catalog_id && work.catalog_type) {
                return (
                  <PosterCard
                    key={work.tmdb_id}
                    href={
                      work.catalog_type === "series"
                        ? `/series/${work.catalog_id}`
                        : `/media/${work.catalog_id}`
                    }
                    imageUrl={imageUrl}
                    title={work.title}
                    subtitle={subtitle}
                  />
                );
              }

              return (
                <div
                  key={work.tmdb_id}
                  className="flex flex-col gap-2 opacity-40"
                >
                  <div className="relative w-full aspect-[2/3] rounded-xl overflow-hidden bg-[#27272a]">
                    {imageUrl ? (
                      <Image
                        src={imageUrl}
                        alt={work.title}
                        fill
                        sizes="200px"
                        className="object-cover"
                        unoptimized
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-[#52525b] text-xs text-center px-2">
                        {work.title}
                      </div>
                    )}
                  </div>
                  <p className="text-xs font-medium text-[#fafafa] line-clamp-2 leading-tight">
                    {work.title}
                  </p>
                  {subtitle && (
                    <p className="text-[11px] text-[#71717a] line-clamp-1 -mt-1">
                      {subtitle}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      ) : (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-[#71717a] text-sm">{t("person.noFilmography")}</p>
        </div>
      )}
    </div>
  );
}

function PersonSkeleton() {
  return (
    <div className="px-4 md:px-12 py-6 md:py-10">
      <Skeleton className="h-5 w-24 mb-8 rounded" />
      <div className="flex gap-8 md:gap-12 mb-12">
        <Skeleton className="w-36 md:w-48 aspect-[2/3] rounded-2xl shrink-0" />
        <div className="flex flex-col gap-4 flex-1 pt-1">
          <Skeleton className="h-9 w-56 rounded-lg" />
          <Skeleton className="h-4 w-40 rounded" />
          <Skeleton className="h-4 w-32 rounded" />
          <div className="flex gap-2">
            <Skeleton className="h-7 w-16 rounded-lg" />
            <Skeleton className="h-7 w-24 rounded-lg" />
          </div>
          <Skeleton className="h-4 w-full max-w-xl rounded" />
          <Skeleton className="h-4 w-full max-w-xl rounded" />
          <Skeleton className="h-4 w-3/4 max-w-lg rounded" />
        </div>
      </div>
      <Skeleton className="h-7 w-48 rounded-lg mb-6" />
      <div className="grid grid-cols-3 md:grid-cols-5 lg:grid-cols-7 gap-3 md:gap-4">
        {Array.from({ length: 14 }).map((_, i) => (
          <div key={i} className="flex flex-col gap-2">
            <Skeleton className="w-full aspect-[2/3] rounded-xl" />
            <Skeleton className="h-3.5 w-3/4 rounded" />
            <Skeleton className="h-3 w-1/2 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}
