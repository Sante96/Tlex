"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import type { PoolWarning } from "@/hooks/player/use-pool-status";

interface PoolWarningOverlayProps {
  warning: PoolWarning;
  poolPressure?: number;
}

const MESSAGES: Record<NonNullable<PoolWarning>, string> = {
  no_clients: "Nessun client disponibile. Lo streaming potrebbe non avviarsi.",
  high_pressure:
    "Pool client quasi pieno. Lo streaming potrebbe essere più lento.",
};

export function PoolWarningOverlay({
  warning,
  poolPressure,
}: PoolWarningOverlayProps) {
  return (
    <AnimatePresence>
      {warning && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.3 }}
          className="absolute top-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-4 py-2 rounded-lg backdrop-blur-md text-sm pointer-events-none"
          style={{
            backgroundColor:
              warning === "no_clients"
                ? "rgba(220, 38, 38, 0.85)"
                : "rgba(234, 179, 8, 0.85)",
          }}
        >
          <AlertTriangle className="w-4 h-4 text-white shrink-0" />
          <span className="text-white font-medium">
            {MESSAGES[warning]}
            {poolPressure !== undefined && warning === "high_pressure" && (
              <span className="ml-1 opacity-75">
                ({Math.round(poolPressure * 100)}%)
              </span>
            )}
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
