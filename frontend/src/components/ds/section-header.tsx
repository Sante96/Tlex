import Link from "next/link";

interface SectionHeaderProps {
  title: string;
  href?: string;
  linkText?: string;
}

export function SectionHeader({
  title,
  href,
  linkText = "Vedi tutto →",
}: SectionHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-5">
      <h2 className="text-2xl font-semibold text-[#fafafa]">{title}</h2>
      {href && (
        <Link
          href={href}
          className="text-sm font-medium text-[#e5a00d] hover:underline focus-visible:outline-none focus-visible:underline focus-visible:ring-2 focus-visible:ring-[#e5a00d] focus-visible:rounded"
        >
          {linkText}
        </Link>
      )}
    </div>
  );
}
