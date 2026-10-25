"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSButton, TVButton } from "@/components/ds";
import { PosterCardSkeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/contexts/auth-context";
import { useIsTV } from "@/hooks/use-platform";
import { triggerScan } from "@/lib/api";
import { useDelayed } from "@/hooks/use-delayed";

/** Poster grids of the library pages: a real grid on phones too (it used to be the home
 * rows' single horizontal strip, so a whole library was one long row). */
export const POSTER_GRID =
  "grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4";
export const TV_POSTER_GRID = "grid grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-4 md:gap-5";

const PAGE_SIZE = 60;

interface LibraryPageProps<T> {
  title: string;
  emptyText: string;
  load: (page: number, pageSize: number) => Promise<{ items: T[]; total: number }>;
  renderItem: (item: T) => ReactNode;
}

/** A library page (movies, series): header with the total, poster grid, "load more". */
export function LibraryPage<T>({ title, emptyText, load, renderItem }: LibraryPageProps<T>) {
  const t = useTranslations();
  const isTV = useIsTV();
  const { user } = useAuth();
  const [items, setItems] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const showSkeleton = useDelayed(loading);
  const [loadingMore, setLoadingMore] = useState(false);
  const [failed, setFailed] = useState(false);
  const [scanning, setScanning] = useState(false);

  const loadFirstPage = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    try {
      const data = await load(1, PAGE_SIZE);
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [load]);

  useEffect(() => {
    loadFirstPage();
  }, [loadFirstPage]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const data = await load(Math.floor(items.length / PAGE_SIZE) + 1, PAGE_SIZE);
      setItems((current) => [...current, ...data.items]);
      setTotal(data.total);
    } catch {
      // the button stays: pressing it again retries
    } finally {
      setLoadingMore(false);
    }
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      await triggerScan(100);
      await loadFirstPage();
    } finally {
      setScanning(false);
    }
  };

  const Button = isTV ? TVButton : DSButton;
  const grid = isTV ? TV_POSTER_GRID : POSTER_GRID;

  return (
    <div className={isTV ? "px-8 py-8" : "px-4 md:px-12 py-6 md:py-8"}>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#fafafa]">{title}</h1>
          {/* The count's line is kept while loading: the header moved down when it arrived */}
          <p className="text-sm text-[#a1a1aa] min-h-5">
            {!loading && !failed && `${total} ${title.toLowerCase()}`}
          </p>
        </div>
        {/* Scanning takes an admin: the button used to fail silently for everyone else */}
        {!isTV && user?.is_admin && (
          <DSButton
            variant="secondary"
            onClick={handleScan}
            disabled={scanning}
            className="!h-9"
            icon={<RefreshCw className={`h-4 w-4 ${scanning ? "animate-spin" : ""}`} />}
          >
            {t("common.refresh")}
          </DSButton>
        )}
      </div>

      {loading ? (
        showSkeleton && (
          <div className={grid}>
            {Array.from({ length: 12 }).map((_, i) => (
              <PosterCardSkeleton key={i} />
            ))}
          </div>
        )
      ) : failed ? (
        <div className="flex flex-col items-center gap-6 py-12 text-[#a1a1aa]">
          {t("common.loadError")}
          <Button onClick={loadFirstPage} icon={<RefreshCw className="h-4 w-4" />}>
            {t("common.retry")}
          </Button>
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 text-[#a1a1aa]">{emptyText}</div>
      ) : (
        <>
          <div className={grid}>{items.map(renderItem)}</div>
          {items.length < total && (
            <div className="flex justify-center mt-8">
              <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? t("common.loading") : t("common.loadMore")}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
