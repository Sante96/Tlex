"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, CheckCircle, AlertCircle, Info } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counterRef = useRef(0);

  const toast = useCallback((message: string, type: ToastType = "info") => {
    const id = ++counterRef.current;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(
      () => setToasts((prev) => prev.filter((t) => t.id !== id)),
      3500,
    );
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-[200] flex flex-col gap-2 items-center pointer-events-none">
        <AnimatePresence mode="sync">
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 12, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.96 }}
              transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
              className="pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg min-w-[240px] max-w-[360px]"
              style={{
                backgroundColor: "rgba(24, 24, 27, 0.97)",
                border: "1px solid rgba(63,63,70,0.6)",
              }}
            >
              {t.type === "success" && (
                <CheckCircle className="h-4 w-4 text-emerald-400 shrink-0" />
              )}
              {t.type === "error" && (
                <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
              )}
              {t.type === "info" && (
                <Info className="h-4 w-4 text-zinc-400 shrink-0" />
              )}
              <span className="text-sm text-white flex-1">{t.message}</span>
              <button
                onClick={() => dismiss(t.id)}
                className="text-zinc-500 hover:text-white transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx.toast;
}
