import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse rounded-lg bg-zinc-800/60", className)} />
  );
}

export function PosterCardSkeleton() {
  return (
    <div className="flex flex-col gap-2 shrink-0">
      <Skeleton className="w-[140px] md:w-[160px] h-[210px] md:h-[240px] rounded-xl" />
      <Skeleton className="h-3.5 w-[100px] rounded" />
      <Skeleton className="h-3 w-[70px] rounded" />
    </div>
  );
}

export function HeroBannerSkeleton() {
  return (
    <div className="w-full animate-pulse">
      <div className="relative w-full aspect-[16/9] md:aspect-[21/9] bg-zinc-800/60 rounded-none" />
    </div>
  );
}

export function DetailPageSkeleton() {
  return (
    <div className="flex flex-col gap-8 px-4 md:px-12 pt-6">
      <HeroBannerSkeleton />
      <div className="flex flex-col gap-3 px-4 md:px-12">
        <Skeleton className="h-8 w-64 rounded-lg" />
        <Skeleton className="h-4 w-40 rounded" />
        <div className="flex gap-3 mt-2">
          <Skeleton className="h-11 w-36 rounded-xl" />
          <Skeleton className="h-11 w-36 rounded-xl" />
        </div>
        <Skeleton className="h-4 w-full max-w-xl rounded mt-2" />
        <Skeleton className="h-4 w-3/4 max-w-lg rounded" />
      </div>
    </div>
  );
}
