"use client";

import { useState } from "react";
import Image, { type ImageProps } from "next/image";
import { cn } from "@/lib/utils";

/**
 * next/image that fades in once it has loaded: backdrops, posters and photos popped in
 * whenever they arrived, after the page had already shown. It fades itself, not an
 * ancestor, so the glass over a backdrop keeps its blur.
 */
export function FadeImage({ className, onLoad, alt, ...props }: ImageProps) {
  const [loaded, setLoaded] = useState(false);
  return (
    <Image
      {...props}
      alt={alt}
      onLoad={(e) => {
        setLoaded(true);
        onLoad?.(e);
      }}
      className={cn(
        "transition-opacity duration-300",
        loaded ? "opacity-100" : "opacity-0",
        className,
      )}
    />
  );
}
