"use client";

import { Clock, RefreshCw, Play, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSButton, DSCard } from "@/components/ds";
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
  const t = useTranslations();
  return (
    <DSCard
      icon={<Clock className="w-5 h-5 text-[#e5a00d]" />}
      title={t("scanner.title")}
      description={t("scanner.description")}
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-[#fafafa]">
            {t("scanner.status")}
          </span>
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
              {t("scanner.autoScan")}
            </span>
            <p className="text-xs text-[#71717a]">{t("scanner.interval")}</p>
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
              <SelectItem value="0">{t("scanner.intervalDisabled")}</SelectItem>
              <SelectItem value="1">{t("scanner.interval1h")}</SelectItem>
              <SelectItem value="3">{t("scanner.interval3h")}</SelectItem>
              <SelectItem value="6">{t("scanner.interval6h")}</SelectItem>
              <SelectItem value="12">{t("scanner.interval12h")}</SelectItem>
              <SelectItem value="24">{t("scanner.interval24h")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {autoScanData && autoScanData.last_scan && (
          <DSCard
            level="secondary"
            className="p-3 rounded-lg shadow-none backdrop-blur-none gap-1"
          >
            <div className="text-sm text-[#71717a]">
              {t("scanner.lastScan")}
            </div>
            <div className="text-lg font-bold">
              {new Date(autoScanData.last_scan).toLocaleString(undefined, {
                day: "2-digit",
                month: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
          </DSCard>
        )}

        <div className="h-px bg-[#27272a]" />

        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-[#fafafa]">
              {t("scanner.triggerScan")}
            </span>
            <p className="text-xs text-[#71717a]">{t("scanner.scanning")}</p>
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
              ? t("scanner.scanning")
              : t("scanner.triggerScan")}
          </DSButton>
        </div>
      </div>
    </DSCard>
  );
}
