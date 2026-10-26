"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Phone, Plus, Loader2 } from "lucide-react";
import { DSButton, DSCard, DSInput } from "@/components/ds";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { sendWorkerCode, verifyWorkerCode } from "@/lib/api";
import { AxiosError } from "axios";
// The flags as inline SVGs, in the bundle: not emoji (Windows has no flag emoji), not
// fetched (the old flag package loaded each one from a CDN)
import {
  IT,
  BE,
  US,
  GB,
  FR,
  DE,
  ES,
  NL,
  CH,
  AT,
  PT,
  PL,
  UA,
  RU,
  JP,
  CN,
  IN,
  BR,
} from "country-flag-icons/react/3x2";

const COUNTRY_PREFIXES = [
  { dial: "+39", iso: "IT", Flag: IT },
  { dial: "+32", iso: "BE", Flag: BE },
  { dial: "+1", iso: "US", Flag: US },
  { dial: "+44", iso: "GB", Flag: GB },
  { dial: "+33", iso: "FR", Flag: FR },
  { dial: "+49", iso: "DE", Flag: DE },
  { dial: "+34", iso: "ES", Flag: ES },
  { dial: "+31", iso: "NL", Flag: NL },
  { dial: "+41", iso: "CH", Flag: CH },
  { dial: "+43", iso: "AT", Flag: AT },
  { dial: "+351", iso: "PT", Flag: PT },
  { dial: "+48", iso: "PL", Flag: PL },
  { dial: "+380", iso: "UA", Flag: UA },
  { dial: "+7", iso: "RU", Flag: RU },
  { dial: "+81", iso: "JP", Flag: JP },
  { dial: "+86", iso: "CN", Flag: CN },
  { dial: "+91", iso: "IN", Flag: IN },
  { dial: "+55", iso: "BR", Flag: BR },
];

type Step = "idle" | "sending" | "code" | "2fa" | "verifying" | "done";

interface AddWorkerCardProps {
  onWorkersChanged: () => void;
}

export function AddWorkerCard({ onWorkersChanged }: AddWorkerCardProps) {
  const t = useTranslations();
  const [step, setStep] = useState<Step>("idle");
  const [prefix, setPrefix] = useState("+39");
  const selectedCountry = COUNTRY_PREFIXES.find((p) => p.dial === prefix);
  const [localNumber, setLocalNumber] = useState("");
  const [code, setCode] = useState("");

  const fullPhone = `${prefix}${localNumber.replace(/\s/g, "")}`;
  const [password2fa, setPassword2fa] = useState("");
  const [error, setError] = useState("");
  // An archive account: saved apart from the workers, never streams
  const [archive, setArchive] = useState(false);
  const [addedArchive, setAddedArchive] = useState(false);

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
        archive,
      );
      if (result.status === "2fa_required") {
        setStep("2fa");
        return;
      }
      setAddedArchive(archive);
      setStep("done");
      setLocalNumber("");
      setCode("");
      setPassword2fa("");
      setArchive(false);
      onWorkersChanged();
      setTimeout(() => setStep("idle"), 2000);
    } catch (err) {
      setError(getErrorMessage(err));
      setStep("code");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent, action: () => void) => {
    if (e.key === "Enter") action();
  };

  return (
    <DSCard
      icon={<Phone className="w-5 h-5 text-plex-orange" />}
      title="Worker Telegram"
    >
      <div className="flex flex-col gap-4">
        {/* Add worker form */}
        {step === "done" ? (
          <p className="text-green-400 text-sm text-center py-2">
            {addedArchive ? t("workers.archiveAdded") : t("workers.addSuccess")}
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {/* Phone input (always visible when not done) */}
            {/* On a phone the button goes under the number: in one row the field was
                squeezed between the prefix and the button */}
            <div className="flex flex-wrap sm:flex-nowrap gap-2">
              <Select
                value={prefix}
                onValueChange={setPrefix}
                disabled={step !== "idle" && step !== "sending"}
              >
                <SelectTrigger
                  className="w-[104px] shrink-0"
                  style={{ height: "40px" }}
                >
                  <span className="flex items-center gap-2 text-sm truncate">
                    {selectedCountry && (
                      <selectedCountry.Flag
                        title={selectedCountry.iso}
                        className="h-3.5 w-auto shrink-0 rounded-[2px]"
                      />
                    )}
                    {prefix}
                  </span>
                </SelectTrigger>
                <SelectContent
                  position="popper"
                  style={{ maxHeight: "200px", overflowY: "auto" }}
                >
                  {COUNTRY_PREFIXES.map((p) => (
                    <SelectItem key={p.dial} value={p.dial}>
                      <span className="flex items-center gap-2">
                        <p.Flag
                          title={p.iso}
                          className="h-3.5 w-auto shrink-0 rounded-[2px]"
                        />
                        {p.dial}
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
                className="flex-1 min-w-0"
              />
              {step === "idle" && (
                <DSButton
                  onClick={handleSendCode}
                  disabled={!localNumber.trim()}
                  icon={<Plus className="w-4 h-4" />}
                  className="w-full sm:w-auto"
                >
                  {t("workers.sendCode")}
                </DSButton>
              )}
              {step === "sending" && (
                <DSButton
                  disabled
                  icon={<Loader2 className="w-4 h-4 animate-spin" />}
                  className="w-full sm:w-auto"
                />
              )}
            </div>

            <div className="flex items-center justify-between gap-3">
              <label
                htmlFor="archive-account"
                className="text-xs text-[#a1a1aa]"
              >
                {t("workers.archive")}
              </label>
              <Switch
                id="archive-account"
                checked={archive}
                onCheckedChange={setArchive}
                disabled={step !== "idle"}
              />
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
