import { RatingBadge } from "./rating-badge";

interface MetaItem {
  text: string;
}

interface MetaRowProps {
  /** TMDB vote_average (0-10), optional */
  voteAverage?: number | null;
  /** Content/parental rating e.g. "TV-MA", "PG-13" */
  contentRating?: string | null;
  items: MetaItem[];
}

export function MetaRow({ voteAverage, contentRating, items }: MetaRowProps) {
  return (
    <div className="flex items-center gap-3 text-sm">
      {contentRating && (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded border border-[#71717a] text-[11px] font-semibold text-[#a1a1aa] tracking-wide">
          {contentRating}
        </span>
      )}
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
