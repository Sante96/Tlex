"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

// The exit animation's length (globals.css, .ds-modal): the parent unmounts it after
const CLOSE_MS = 160;

/**
 * A modal on the native <dialog>: the page behind is inert and doesn't scroll, focus stays
 * inside; Escape, Back (TV remote, phone), a click outside and any button marked
 * data-modal-close close it, animated. Rendered while open: the parent unmounts it to
 * close, which it does once the exit animation has played.
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

  const [closing, setClosing] = useState(false);
  const requestClose = useCallback(() => setClosing(true), []);
  useEffect(() => {
    if (!closing) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const timer = setTimeout(onClose, reduced ? 0 : CLOSE_MS);
    return () => clearTimeout(timer);
  }, [closing, onClose]);

  useBackToClose(true, requestClose);

  return (
    <dialog
      ref={ref}
      {...aria}
      data-closing={closing || undefined}
      // Escape: animated out, then the parent unmounts it
      onCancel={(e) => {
        e.preventDefault();
        requestClose();
      }}
      // The dialog itself is the transparent area around the panel. Pressed there too:
      // selecting an input's text and releasing outside closed the form
      onPointerDown={(e) =>
        (downOnBackdrop.current = e.target === e.currentTarget)
      }
      onClick={(e) => {
        const onBackdrop = downOnBackdrop.current && e.target === e.currentTarget;
        // The modals' own X and Cancel buttons, so they animate out too
        const closeButton = (e.target as Element).closest("[data-modal-close]");
        if (onBackdrop || closeButton) requestClose();
      }}
      className="ds-modal fixed inset-0 m-0 h-full w-full max-h-none max-w-none bg-transparent p-4 open:flex items-center justify-center backdrop:bg-black/60 backdrop:backdrop-blur-sm outline-none"
    >
      <div
        className={cn(
          "ds-modal-panel w-full max-w-md",
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
