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

