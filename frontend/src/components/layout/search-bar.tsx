"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, Film, Tv, Loader2, ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { getMediaList, getSeriesList } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";
import Image from "next/image";

interface SearchResult {
  id: number;
  title: string;
  poster_path: string | null;
  type: "movie" | "series";
  year?: string;
}

const PANEL_STYLE: React.CSSProperties = {
  backgroundColor: "rgba(10,10,10,0.88)",
  border: "1px solid rgba(255,255,255,0.07)",
};

function ResultRow({
  result,
  onSelect,
}: {
  result: SearchResult;
  onSelect: (r: SearchResult) => void;
}) {
  return (
    <button
      onClick={() => onSelect(result)}
      className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/[0.07] transition-colors text-left group"
    >
      <div className="w-10 h-[60px] rounded-md overflow-hidden shrink-0 bg-white/[0.04] border border-white/[0.06]">
        {result.poster_path ? (
          <Image
            src={getTmdbImageUrl(result.poster_path, "w300") || ""}
            alt={result.title}
            width={40}
            height={60}
            className="object-cover w-full h-full"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            {result.type === "movie" ? (
              <Film className="h-4 w-4 text-white/20" />
            ) : (
              <Tv className="h-4 w-4 text-white/20" />
            )}
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white/85 truncate group-hover:text-white transition-colors leading-tight">
          {result.title}
        </p>
        {result.year && (
          <p className="text-xs text-white/30 mt-0.5">{result.year}</p>
        )}
      </div>
      <ArrowRight className="h-3.5 w-3.5 text-white/20 group-hover:text-white/50 transition-all group-hover:translate-x-0.5 shrink-0" />
    </button>
  );
}

export function SearchBar({ className }: { className?: string }) {
  const router = useRouter();
  const t = useTranslations();
  const [query, setQuery] = useState("");
  const [movies, setMovies] = useState<SearchResult[]>([]);
  const [series, setSeries] = useState<SearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  const hasResults = movies.length > 0 || series.length > 0;

  const search = useCallback(async (term: string) => {
    if (term.length < 2) {
      setMovies([]);
      setSeries([]);
      setIsOpen(false);
      return;
    }
    setLoading(true);
    try {
      const [mediaRes, seriesRes] = await Promise.all([
        getMediaList({ search: term, limit: 4, media_type: "MOVIE" }),
        getSeriesList({ search: term, page_size: 4 }),
      ]);
      setMovies(
        mediaRes.items.map((m) => ({
          id: m.id,
          title: m.title,
          poster_path: m.poster_path,
          type: "movie" as const,
          year: m.release_date
            ? new Date(m.release_date).getFullYear().toString()
            : undefined,
        })),
      );
      setSeries(
        seriesRes.items.map((s) => ({
          id: s.id,
          title: s.title,
          poster_path: s.poster_path,
          type: "series" as const,
          year: s.first_air_date
            ? new Date(s.first_air_date).getFullYear().toString()
            : undefined,
        })),
      );
      setIsOpen(true);
    } catch {
      setMovies([]);
      setSeries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChange = (value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(value.trim()), 300);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && query.trim().length >= 2) {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      search(query.trim());
    }
    if (e.key === "Escape") setIsOpen(false);
  };

  const handleSelect = (result: SearchResult) => {
    setIsOpen(false);
    setQuery("");
    router.push(
      result.type === "movie" ? `/media/${result.id}` : `/series/${result.id}`,
    );
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const showPanel = isOpen && query.length >= 2;

  return (
    <div
      ref={containerRef}
      className={`relative ${className ?? ""}`}
      style={className ? undefined : { width: 320 }}
    >
      {/* Input */}
      <div
        className="group flex items-center gap-2 h-9 px-3 rounded-lg border border-white/5 backdrop-blur-sm transition-all duration-150
          hover:border-white/15 focus-within:border-[#e5a00d] focus-within:border-2 focus-within:px-[11px]"
        style={{ backgroundColor: "rgba(255,255,255,0.08)" }}
      >
        {loading ? (
          <Loader2 className="h-4 w-4 shrink-0 text-[#e5a00d] animate-spin" />
        ) : (
          <Search className="h-4 w-4 shrink-0 text-[#71717a] group-hover:text-[#a1a1aa] group-focus-within:text-[#e5a00d] transition-colors" />
        )}
        <input
          type="search"
          placeholder={t("search.placeholder")}
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => hasResults && setIsOpen(true)}
          className="bg-transparent border-none outline-none text-sm text-[#fafafa] placeholder:text-[#71717a] w-full"
        />
      </div>

      {/* Results panel */}
      {showPanel && (
        <div
          className="absolute top-full mt-2 z-50 rounded-2xl shadow-[0_16px_48px_rgba(0,0,0,0.6)] backdrop-blur-xl"
          style={{
            ...PANEL_STYLE,
            left: 0,
            minWidth: "360px",
            right: className ? 0 : "auto",
          }}
        >
          <div className="rounded-2xl overflow-hidden">
            {hasResults ? (
              <div className="p-2 flex flex-col gap-1">
                {/* Films section */}
                {movies.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 px-3 pt-1.5 pb-1">
                      <Film className="h-3 w-3 text-blue-400" />
                      <span className="text-[10px] font-semibold text-blue-400 uppercase tracking-wider">
                        {t("search.movies")}
                      </span>
                    </div>
                    {movies.map((m) => (
                      <ResultRow
                        key={`movie-${m.id}`}
                        result={m}
                        onSelect={handleSelect}
                      />
                    ))}
                  </div>
                )}
                {/* Divider */}
                {movies.length > 0 && series.length > 0 && (
                  <div className="h-px bg-white/[0.05] mx-3 my-1" />
                )}
                {/* Series section */}
                {series.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 px-3 pt-1.5 pb-1">
                      <Tv className="h-3 w-3 text-purple-400" />
                      <span className="text-[10px] font-semibold text-purple-400 uppercase tracking-wider">
                        {t("search.series")}
                      </span>
                    </div>
                    {series.map((s) => (
                      <ResultRow
                        key={`series-${s.id}`}
                        result={s}
                        onSelect={handleSelect}
                      />
                    ))}
                  </div>
                )}
              </div>
            ) : !loading ? (
              <div className="flex flex-col items-center gap-2 py-8 px-4">
                <Search className="h-8 w-8 text-white/10" />
                <p className="text-sm text-white/30 text-center">
                  {t("search.noResults")}{" "}
                  <span className="text-white/50">&ldquo;{query}&rdquo;</span>
                </p>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
