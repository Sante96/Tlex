import { Star } from "lucide-react";

interface RatingBadgeProps {
  /** TMDB vote_average (0-10), will be displayed as percentage */
  voteAverage: number;
}

export function RatingBadge({ voteAverage }: RatingBadgeProps) {
  const percent = Math.round(voteAverage * 10);
  if (percent <= 0) return null;

  return (
    <span className="inline-flex items-center gap-1 px-2 h-6 rounded bg-[#16a34a] text-white text-xs font-semibold">
      <Star className="h-3 w-3" />
      {percent}%
    </span>
  );
}
