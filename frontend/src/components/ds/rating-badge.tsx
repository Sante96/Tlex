import Image from "next/image";

interface RatingBadgeProps {
  /** TMDB vote_average (0-10), will be displayed as percentage */
  voteAverage: number;
}

export function RatingBadge({ voteAverage }: RatingBadgeProps) {
  const percent = Math.round(voteAverage * 10);
  if (percent <= 0) return null;

  return (
    <span className="inline-flex items-center gap-2">
      <Image
        src="/tmdb-logo.svg"
        alt="TMDB"
        width={60}
        height={8}
        className="opacity-80"
        unoptimized
      />
      <span className="text-sm font-semibold text-[#e4e4e7]">{percent}%</span>
    </span>
  );
}
