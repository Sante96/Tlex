import { RatingBadge } from "./rating-badge";

interface MetaItem {
  text: string;
}

interface MetaRowProps {
  /** TMDB vote_average (0-10), optional */
  voteAverage?: number | null;
  items: MetaItem[];
}

export function MetaRow({ voteAverage, items }: MetaRowProps) {
  return (
    <div className="flex items-center gap-3 text-sm">
      {voteAverage && voteAverage > 0 && (
        <RatingBadge voteAverage={voteAverage} />
      )}
      {items.map((item, i) => (
        <span key={i} className="contents">
          {i > 0 && <span className="text-[#52525b]">•</span>}
          <span className="text-[#e4e4e7]">{item.text}</span>
        </span>
      ))}
    </div>
  );
}
