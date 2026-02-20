"use client";

import { useState, useEffect, useCallback } from "react";
import { getPoolStatus, type PoolStatus } from "@/lib/api";

export type PoolWarning = "no_clients" | "high_pressure" | null;

interface UsePoolStatusOptions {
  /** Poll interval in ms (default: 10000) */
  pollInterval?: number;
  /** Only poll while active (default: true) */
  enabled?: boolean;
}

interface UsePoolStatusReturn {
  poolStatus: PoolStatus | null;
  warning: PoolWarning;
  refresh: () => Promise<void>;
}

export function usePoolStatus(
  options: UsePoolStatusOptions = {},
): UsePoolStatusReturn {
  const { pollInterval = 10000, enabled = true } = options;
  const [poolStatus, setPoolStatus] = useState<PoolStatus | null>(null);
  const [warning, setWarning] = useState<PoolWarning>(null);

  const refresh = useCallback(async () => {
    const status = await getPoolStatus();
    if (!status) return;

    setPoolStatus(status);

    if (status.clients_available === 0 && status.total_clients === 0) {
      setWarning("no_clients");
    } else if (status.pool_pressure >= 0.9) {
      setWarning("high_pressure");
    } else {
      setWarning(null);
    }
  }, []);

  // Initial fetch + polling
  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;
    const doFetch = async () => {
      if (cancelled) return;
      await refresh();
    };

    // Deferred initial fetch to avoid synchronous setState in effect
    const timeoutId = setTimeout(doFetch, 0);
    const interval = setInterval(doFetch, pollInterval);
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
      clearInterval(interval);
    };
  }, [enabled, pollInterval, refresh]);

  return { poolStatus, warning, refresh };
}
