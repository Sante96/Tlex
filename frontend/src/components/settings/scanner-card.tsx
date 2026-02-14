"use client";

import { Clock, RefreshCw, Play, Loader2 } from "lucide-react";
import { DSButton } from "@/components/ds";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  setAutoScanInterval,
  type AutoScanStatus,
  type ScanStatus,
} from "@/lib/api";

interface ScannerCardProps {
  autoScanData: AutoScanStatus | null;
  scanStatus: ScanStatus | null;
  loading: boolean;
  triggering: boolean;
  onRefresh: () => void;
  onTriggerScan: () => void;
  onAutoScanChange: (data: AutoScanStatus) => void;
}

export function ScannerCard({
  autoScanData,
  scanStatus,
  loading,
  triggering,
  onRefresh,
  onTriggerScan,
  onAutoScanChange,
}: ScannerCardProps) {
  return (
    <div className="bg-zinc-900 rounded-lg p-6">
      <div className="flex items-center gap-3 mb-4">
        <Clock className="w-5 h-5 text-plex-orange" />
        <div>
          <h2 className="font-semibold">Scanner Automatico</h2>
          <p className="text-xs text-muted-foreground">
            Scansione periodica dei canali Telegram
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-[#fafafa]">Stato</span>
          <DSButton
            variant="ghost"
            onClick={onRefresh}
            disabled={loading}
            className="!h-8 !w-8 !px-0"
            icon={
              <RefreshCw
                className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
              />
            }
          />
        </div>

        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-[#fafafa]">
              Intervallo auto-scan
            </span>
            <p className="text-xs text-muted-foreground">
              Frequenza scansione automatica
            </p>
          </div>
          <Select
            value={String(autoScanData?.interval_hours || 0)}
            onValueChange={async (value) => {
              try {
                const result = await setAutoScanInterval(parseInt(value));
                onAutoScanChange(result);
              } catch {
                // Failed to set interval
              }
            }}
          >
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="0">Disattivo</SelectItem>
              <SelectItem value="1">1 ora</SelectItem>
              <SelectItem value="3">3 ore</SelectItem>
              <SelectItem value="6">6 ore</SelectItem>
              <SelectItem value="12">12 ore</SelectItem>
              <SelectItem value="24">24 ore</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {autoScanData && autoScanData.last_scan && (
          <div className="bg-zinc-800 rounded-lg p-3">
            <div className="text-sm text-muted-foreground mb-1">
              Ultimo scan
            </div>
            <div className="text-lg font-bold">
              {new Date(autoScanData.last_scan).toLocaleString("it-IT", {
                day: "2-digit",
                month: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
          </div>
        )}

        <div className="h-px bg-[#27272a]" />

        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-[#fafafa]">
              Scan manuale
            </span>
            <p className="text-xs text-muted-foreground">
              Avvia una scansione immediata
            </p>
          </div>
          <DSButton
            onClick={onTriggerScan}
            disabled={triggering || scanStatus?.is_scanning}
            icon={
              triggering || scanStatus?.is_scanning ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )
            }
          >
            {triggering || scanStatus?.is_scanning
              ? "Scansione..."
              : "Avvia scan"}
          </DSButton>
        </div>
      </div>
    </div>
  );
}
