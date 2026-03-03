"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

interface ExpandableOverviewProps {
  text: string;
  maxChars?: number;
  className?: string;
}

export function ExpandableOverview({
  text,
  maxChars = 320,
  className,
}: ExpandableOverviewProps) {
  const t = useTranslations("common");
  const [expanded, setExpanded] = useState(false);
  const isLong = text.length > maxChars;

  const displayText =
    isLong && !expanded ? text.slice(0, maxChars) + "…" : text;

  return (
    <div className={cn("max-w-3xl", className)}>
      <p className="text-sm text-[#d4d4d8] leading-relaxed">{displayText}</p>
      {isLong && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-1 flex items-center gap-1 text-sm font-medium text-[#e5a00d] hover:text-[#d4940c] transition-colors"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-4 w-4" />
              {t("readLess")}
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4" />
              {t("readMore")}
            </>
          )}
        </button>
      )}
    </div>
  );
}
