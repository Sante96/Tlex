"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useBackToClose } from "@/hooks/use-back-to-close";

interface DSModalProps {
  onClose: () => void;
  children: React.ReactNode;
  /** The panel's size and layout */
  className?: string;
  /** No glass panel: the children draw their own (the trailer's video) */
  bare?: boolean;
  "aria-label"?: string;
}

/**
 * A modal on the native <dialog>: the page behind is inert and focus stays inside, Escape,
 * Back (TV remote, phone) and a click outside close it. Rendered while open: the parent
 * unmounts it to close.
 */
export function DSModal({
  onClose,
  children,
  className,
  bare,
  ...aria
}: DSModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const downOnBackdrop = useRef(false);
  // The button that opened it gets the focus back on close (the TV's focus otherwise fell
  // to the top of the page)
  const [opener] = useState(() =>
    typeof document === "undefined"
      ? null
      : (document.activeElement as HTMLElement | null),
  );

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    dialog.showModal();
    // showModal focuses the first control. React's autoFocus runs earlier, while the
    // dialog is still closed and hidden, so it focuses nothing: mark the field instead
    dialog.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    return () => {
      dialog.close();
      if (opener?.isConnected) opener.focus();
    };
  }, [opener]);

  useBackToClose(true, onClose);

  return (
    <dialog
      ref={ref}
      {...aria}
      // Escape: the parent closes it, by unmounting
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      // The dialog itself is the transparent area around the panel. Pressed there too:
      // selecting an input's text and releasing outside closed the form
      onPointerDown={(e) =>
        (downOnBackdrop.current = e.target === e.currentTarget)
      }
      onClick={(e) =>
        downOnBackdrop.current && e.target === e.currentTarget && onClose()
      }
      className="fixed inset-0 m-0 h-full w-full max-h-none max-w-none bg-transparent p-4 open:flex items-center justify-center backdrop:bg-black/60 backdrop:backdrop-blur-sm outline-none"
    >
      <div
        className={cn(
          "w-full max-w-md",
          !bare &&
            "rounded-2xl p-6 glass shadow-[0_24px_48px_rgba(0,0,0,0.6)]",
          className,
        )}
      >
        {children}
      </div>
    </dialog>
  );
}
