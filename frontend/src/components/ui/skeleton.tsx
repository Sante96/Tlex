import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse rounded-lg bg-[#27272a]", className)} />
  );
}

export function PosterCardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse shrink-0", className)}>
      <div className="aspect-[2/3] bg-[#27272a] rounded-lg" />
      <div className="h-4 w-3/4 bg-[#27272a] rounded mt-2" />
      <div className="h-3 w-1/2 bg-[#27272a] rounded mt-1" />
    </div>
  );
}

export function HeroBannerSkeleton() {
  return (
    <div className="w-full animate-pulse">
      <div className="relative w-full aspect-[16/9] md:aspect-[21/9] bg-[#27272a] rounded-none" />
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
