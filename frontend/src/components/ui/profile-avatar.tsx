"use client";

import * as React from "react";
import Image from "next/image";
import { cn } from "@/lib/utils";

export interface ProfileAvatarProps {
  src?: string;
  name: string;
  size?: "sm" | "md" | "lg" | "xl";
  borderColor?: string;
  className?: string;
  onClick?: () => void;
  selected?: boolean;
}

const sizeClasses = {
  sm: "w-10 h-10",
  md: "w-16 h-16",
  lg: "w-24 h-24",
  xl: "w-32 h-32",
};

const borderSizeClasses = {
  sm: "ring-2",
  md: "ring-[3px]",
  lg: "ring-4",
  xl: "ring-4",
};

const textSizeClasses = {
  sm: "text-sm",
  md: "text-xl",
  lg: "text-3xl",
  xl: "text-4xl",
};

export function ProfileAvatar({
  src,
  name,
  size = "md",
  borderColor = "ring-plex-orange",
  className,
  onClick,
  selected = false,
}: ProfileAvatarProps) {
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  const sharedClassName = cn(
    "relative rounded-full overflow-hidden transition-all duration-200",
    "bg-zinc-800 flex items-center justify-center",
    sizeClasses[size],
    borderSizeClasses[size],
    selected ? borderColor : "ring-transparent",
    className,
  );

  const content = src ? (
    <Image
      src={src}
      alt={name}
      fill
      className="object-cover"
      sizes={
        size === "xl"
          ? "128px"
          : size === "lg"
            ? "96px"
            : size === "md"
              ? "64px"
              : "40px"
      }
    />
  ) : (
    <span className={cn("font-semibold text-zinc-400", textSizeClasses[size])}>
      {initials}
    </span>
  );

  // Use div when no onClick (to avoid nested button issues)
  if (!onClick) {
    return <div className={sharedClassName}>{content}</div>;
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        sharedClassName,
        "hover:scale-105 hover:brightness-110 hover:ring-zinc-600",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-plex-orange",
        "cursor-pointer",
      )}
    >
      {content}
    </button>
  );
}

export const PROFILE_AVATARS = [
  { id: "avatar-01", name: "Avatar 1", src: "/avatars/avatar-01.png" },
  { id: "avatar-02", name: "Avatar 2", src: "/avatars/avatar-02.png" },
  { id: "avatar-03", name: "Avatar 3", src: "/avatars/avatar-03.png" },
  { id: "avatar-04", name: "Avatar 4", src: "/avatars/avatar-04.png" },
  { id: "avatar-05", name: "Avatar 5", src: "/avatars/avatar-05.png" },
  { id: "avatar-06", name: "Avatar 6", src: "/avatars/avatar-06.png" },
  { id: "avatar-07", name: "Avatar 7", src: "/avatars/avatar-07.png" },
  { id: "avatar-08", name: "Avatar 8", src: "/avatars/avatar-08.png" },
  { id: "avatar-09", name: "Avatar 9", src: "/avatars/avatar-09.png" },
] as const;

export type ProfileAvatarId = (typeof PROFILE_AVATARS)[number]["id"];
