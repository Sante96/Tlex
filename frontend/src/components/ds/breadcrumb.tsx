"use client";

import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface DSBreadcrumbProps {
  items: BreadcrumbItem[];
}

export function DSBreadcrumb({ items }: DSBreadcrumbProps) {
  const router = useRouter();

  return (
    <div className="flex items-center gap-2">
      {/* Back button */}
      <button
        type="button"
        onClick={() => router.back()}
        className="flex items-center justify-center w-9 h-9 rounded-lg bg-[#27272a] hover:bg-[#3f3f46] transition-colors shrink-0"
      >
        <ChevronLeft className="h-5 w-5 text-[#fafafa]" />
      </button>

      {/* Crumbs */}
      {items.map((item, i) => {
        const isLast = i === items.length - 1;

        return (
          <div key={i} className="flex items-center gap-2">
            {i > 0 && <span className="text-[#52525b] text-sm">/</span>}

            {isLast ? (
              <span className="text-sm font-medium text-[#fafafa]">
                {item.label}
              </span>
            ) : item.href ? (
              <button
                type="button"
                onClick={() => router.push(item.href!)}
                className={cn(
                  "text-sm text-[#a1a1aa] transition-all",
                  "hover:text-[#fafafa] hover:bg-[#27272a] hover:px-2.5 hover:py-1 hover:rounded-md",
                )}
              >
                {item.label}
              </button>
            ) : (
              <span className="text-sm text-[#a1a1aa]">{item.label}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
