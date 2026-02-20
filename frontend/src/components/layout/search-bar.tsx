"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, Film, Tv, Loader2 } from "lucide-react";
import { getMediaList, getSeriesList } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";
import Image from "next/image";

interface SearchResult {
  id: number;
  title: string;
  poster_path: string | null;
  type: "movie" | "series";
  subtitle?: string;
}

export function SearchBar() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  const search = useCallback(async (term: string) => {
    if (term.length < 2) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    setLoading(true);
    try {
      const [mediaRes, seriesRes] = await Promise.all([
        getMediaList({ search: term, limit: 5, media_type: "MOVIE" }),
        getSeriesList({ search: term, page_size: 5 }),
      ]);

      const movieResults: SearchResult[] = mediaRes.items.map((m) => ({
        id: m.id,
        title: m.title,
        poster_path: m.poster_path,
        type: "movie" as const,
        subtitle: m.release_date
          ? new Date(m.release_date).getFullYear().toString()
          : undefined,
      }));

      const seriesResults: SearchResult[] = seriesRes.items.map((s) => ({
        id: s.id,
        title: s.title,
        poster_path: s.poster_path,
        type: "series" as const,
        subtitle: s.first_air_date
          ? new Date(s.first_air_date).getFullYear().toString()
          : undefined,
      }));

      setResults([...movieResults, ...seriesResults]);
      setIsOpen(true);
    } catch {
      setResults([]);
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
    if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  const handleSelect = (result: SearchResult) => {
    setIsOpen(false);
    setQuery("");
    if (result.type === "movie") {
      router.push(`/media/${result.id}`);
    } else {
      router.push(`/series/${result.id}`);
    }
  };

  // Close on click outside
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

  return (
    <div ref={containerRef} className="relative" style={{ width: 320 }}>
      <div
        className="group flex items-center gap-2 h-9 px-3 rounded-lg border border-white/5 transition-all duration-150
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
          placeholder="Cerca..."
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => results.length > 0 && setIsOpen(true)}
          className="bg-transparent border-none outline-none text-sm text-[#fafafa] placeholder:text-[#71717a] w-full"
        />
      </div>

      {/* Dropdown results */}
      {isOpen && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-[#1c1c1e] border border-[#27272a] rounded-lg shadow-xl overflow-hidden z-50 max-h-[400px] overflow-y-auto">
          {results.map((result) => (
            <button
              key={`${result.type}-${result.id}`}
              onClick={() => handleSelect(result)}
              className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-[#27272a] transition-colors text-left"
            >
              {result.poster_path ? (
                <Image
                  src={getTmdbImageUrl(result.poster_path, "w300") || ""}
                  alt={result.title}
                  width={32}
                  height={48}
                  className="rounded object-cover shrink-0"
                />
              ) : (
                <div className="w-8 h-12 bg-[#27272a] rounded shrink-0 flex items-center justify-center">
                  {result.type === "movie" ? (
                    <Film className="h-4 w-4 text-[#52525b]" />
                  ) : (
                    <Tv className="h-4 w-4 text-[#52525b]" />
                  )}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-[#fafafa] truncate">
                  {result.title}
                </p>
                <div className="flex items-center gap-1.5">
                  {result.type === "movie" ? (
                    <Film className="h-3 w-3 text-[#71717a]" />
                  ) : (
                    <Tv className="h-3 w-3 text-[#71717a]" />
                  )}
                  <span className="text-xs text-[#71717a]">
                    {result.type === "movie" ? "Film" : "Serie TV"}
                    {result.subtitle && ` · ${result.subtitle}`}
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* No results */}
      {isOpen && results.length === 0 && query.length >= 2 && !loading && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-[#1c1c1e] border border-[#27272a] rounded-lg shadow-xl p-4 z-50">
          <p className="text-sm text-[#71717a] text-center">Nessun risultato</p>
        </div>
      )}
    </div>
  );
}
