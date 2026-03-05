"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Phone, Trash2, Plus, Loader2, Crown } from "lucide-react";
import ReactCountryFlag from "react-country-flag";
import { DSButton, DSCard, DSInput } from "@/components/ds";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import {
  sendWorkerCode,
  verifyWorkerCode,
  deleteWorker,
  type WorkerInfo,
} from "@/lib/api";
import { AxiosError } from "axios";

const COUNTRY_PREFIXES = [
  { dial: "+39", iso: "IT" },
  { dial: "+32", iso: "BE" },
  { dial: "+1",  iso: "US" },
  { dial: "+44", iso: "GB" },
  { dial: "+33", iso: "FR" },
  { dial: "+49", iso: "DE" },
  { dial: "+34", iso: "ES" },
  { dial: "+31", iso: "NL" },
  { dial: "+41", iso: "CH" },
  { dial: "+43", iso: "AT" },
  { dial: "+351", iso: "PT" },
  { dial: "+48", iso: "PL" },
  { dial: "+380", iso: "UA" },
  { dial: "+7",  iso: "RU" },
  { dial: "+81", iso: "JP" },
  { dial: "+86", iso: "CN" },
  { dial: "+91", iso: "IN" },
  { dial: "+55", iso: "BR" },
];

type Step = "idle" | "sending" | "code" | "2fa" | "verifying" | "done";

interface AddWorkerCardProps {
  workers: WorkerInfo[];
  onWorkersChanged: () => void;
}

export function AddWorkerCard({
  workers,
  onWorkersChanged,
}: AddWorkerCardProps) {
  const t = useTranslations();
  const [step, setStep] = useState<Step>("idle");
  const [prefix, setPrefix] = useState("+39");
  const selectedCountry = COUNTRY_PREFIXES.find((p) => p.dial === prefix);
  const [localNumber, setLocalNumber] = useState("");
  const [code, setCode] = useState("");

  const fullPhone = `${prefix}${localNumber.replace(/\s/g, "")}`;
  const [password2fa, setPassword2fa] = useState("");
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const getErrorMessage = (err: unknown): string => {
    if (err instanceof AxiosError && err.response?.data?.detail) {
      return err.response.data.detail;
    }
    return t("workers.unknownError");
  };

  const handleSendCode = async () => {
    if (!localNumber.trim()) return;
    setError("");
    setStep("sending");
    try {
      await sendWorkerCode(fullPhone);
      setStep("code");
    } catch (err) {
      setError(getErrorMessage(err));
      setStep("idle");
    }
  };

  const handleVerifyCode = async (twoFaPassword?: string) => {
    setError("");
    setStep("verifying");
    try {
      const result = await verifyWorkerCode(
        fullPhone,
        code.trim(),
        twoFaPassword,
      );
      if (result.status === "2fa_required") {
        setStep("2fa");
        return;
      }
      setStep("done");
      setLocalNumber("");
      setCode("");
      setPassword2fa("");
      onWorkersChanged();
      setTimeout(() => setStep("idle"), 2000);
    } catch (err) {
      setError(getErrorMessage(err));
      setStep("code");
    }
  };

  const handleDelete = async (workerId: number) => {
    setDeletingId(workerId);
    try {
      await deleteWorker(workerId);
      onWorkersChanged();
    } catch (err) {
      setError(getErrorMessage(err));
    }
    setDeletingId(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent, action: () => void) => {
    if (e.key === "Enter") action();
  };

  return (
    <DSCard
      icon={<Phone className="w-5 h-5 text-[#e5a00d]" />}
      title="Worker Telegram"
    >
      <div className="flex flex-col gap-4">
        {/* Existing workers list */}
        {workers.length > 0 && (
          <div className="flex flex-col gap-2">
            {workers.map((w) => (
              <DSCard
                key={w.id}
                level="secondary"
                className="py-2 px-3 rounded-lg shadow-none backdrop-blur-none flex-row items-center justify-between gap-0"
              >
                <div className="flex items-center gap-2">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      w.status === "ACTIVE"
                        ? "bg-green-500"
                        : w.status === "FLOOD_WAIT"
                          ? "bg-yellow-500"
                          : "bg-red-500"
                    }`}
                  />
                  <span className="text-sm text-[#fafafa]">****{w.phone}</span>
                  {w.is_premium && (
                    <Crown className="w-3.5 h-3.5 text-[#e5a00d]" />
                  )}
                  <span className="text-xs text-[#71717a]">
                    {w.clients_total} client{w.clients_total !== 1 ? "s" : ""}
                  </span>
                </div>
                <button
                  onClick={() => handleDelete(w.id)}
                  disabled={deletingId === w.id}
                  className="text-[#71717a] hover:text-red-400 transition-colors disabled:opacity-50"
                >
                  {deletingId === w.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </button>
              </DSCard>
            ))}
          </div>
        )}

        {/* Add worker form */}
        {step === "done" ? (
          <p className="text-green-400 text-sm text-center py-2">
            {t("workers.addSuccess")}
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {/* Phone input (always visible when not done) */}
            <div className="flex gap-2">
              <Select
                value={prefix}
                onValueChange={setPrefix}
                disabled={step !== "idle" && step !== "sending"}
              >
                <SelectTrigger className="w-[120px] shrink-0" style={{ height: "40px" }}>
                  <div className="flex items-center gap-1.5 truncate">
                    {selectedCountry && (
                      <ReactCountryFlag
                        countryCode={selectedCountry.iso}
                        svg
                        style={{ width: "1.2em", height: "1.2em" }}
                      />
                    )}
                    <span className="text-sm">{prefix}</span>
                  </div>
                </SelectTrigger>
                <SelectContent position="popper" style={{ maxHeight: "200px", overflowY: "auto" }}>
                  {COUNTRY_PREFIXES.map((p) => (
                    <SelectItem key={p.dial} value={p.dial}>
                      <span className="flex items-center gap-2">
                        <ReactCountryFlag
                          countryCode={p.iso}
                          svg
                          style={{ width: "1.2em", height: "1.2em" }}
                        />
                        <span>{p.iso} {p.dial}</span>
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <DSInput
                type="tel"
                placeholder="460 20 58 06"
                value={localNumber}
                onChange={(e) => setLocalNumber(e.target.value)}
                onKeyDown={(e) => handleKeyDown(e, handleSendCode)}
                disabled={step !== "idle" && step !== "sending"}
                className="flex-1"
              />
              {step === "idle" && (
                <DSButton
                  onClick={handleSendCode}
                  disabled={!localNumber.trim()}
                  icon={<Plus className="w-4 h-4" />}
                >
                  {t("workers.sendCode")}
                </DSButton>
              )}
              {step === "sending" && (
                <DSButton
                  disabled
                  icon={<Loader2 className="w-4 h-4 animate-spin" />}
                />
              )}
            </div>

            {/* Code input */}
            {(step === "code" || step === "verifying") && (
              <div className="flex gap-2">
                <DSInput
                  type="text"
                  placeholder={t("workers.verifyCodePlaceholder")}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  onKeyDown={(e) => handleKeyDown(e, () => handleVerifyCode())}
                  disabled={step === "verifying"}
                  className="flex-1"
                  autoFocus
                />
                <DSButton
                  onClick={() => handleVerifyCode()}
                  disabled={!code.trim() || step === "verifying"}
                  icon={
                    step === "verifying" ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : undefined
                  }
                >
                  {step !== "verifying" && t("workers.verify")}
                </DSButton>
              </div>
            )}

            {/* 2FA password input */}
            {step === "2fa" && (
              <div className="flex flex-col gap-2">
                <p className="text-xs text-[#a1a1aa]">
                  {t("workers.twoFaInfo")}
                </p>
                <div className="flex gap-2">
                  <DSInput
                    type="password"
                    placeholder={t("workers.twoFaPlaceholder")}
                    value={password2fa}
                    onChange={(e) => setPassword2fa(e.target.value)}
                    onKeyDown={(e) =>
                      handleKeyDown(e, () => handleVerifyCode(password2fa))
                    }
                    className="flex-1"
                    autoFocus
                  />
                  <DSButton
                    onClick={() => handleVerifyCode(password2fa)}
                    disabled={!password2fa.trim()}
                  >
                    {t("common.confirm")}
                  </DSButton>
                </div>
              </div>
            )}

            {error && <p className="text-red-500 text-xs">{error}</p>}
          </div>
        )}
      </div>
    </DSCard>
  );
}
