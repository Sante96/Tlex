"use client";

import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import { DSButton } from "@/components/ds";

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
      <DSButton
        type="button"
        variant="secondary"
        onClick={() => router.back()}
        className="!h-9 !w-9 !px-0 shrink-0"
        icon={<ChevronLeft className="h-5 w-5" />}
      />

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
                  "text-sm text-[#a1a1aa] transition-all rounded-md",
                  "hover:text-[#fafafa] hover:bg-[#27272a] hover:px-2.5 hover:py-1",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e5a00d] focus-visible:px-2.5 focus-visible:py-1",
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
