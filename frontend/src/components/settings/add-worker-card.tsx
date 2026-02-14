"use client";

import { useState } from "react";
import { Phone, Trash2, Plus, Loader2, Crown } from "lucide-react";
import { DSCard } from "@/components/ds";
import {
  sendWorkerCode,
  verifyWorkerCode,
  deleteWorker,
  type WorkerInfo,
} from "@/lib/api";
import { AxiosError } from "axios";

type Step = "idle" | "sending" | "code" | "2fa" | "verifying" | "done";

interface AddWorkerCardProps {
  workers: WorkerInfo[];
  onWorkersChanged: () => void;
}

export function AddWorkerCard({
  workers,
  onWorkersChanged,
}: AddWorkerCardProps) {
  const [step, setStep] = useState<Step>("idle");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password2fa, setPassword2fa] = useState("");
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const getErrorMessage = (err: unknown): string => {
    if (err instanceof AxiosError && err.response?.data?.detail) {
      return err.response.data.detail;
    }
    return "Errore sconosciuto";
  };

  const handleSendCode = async () => {
    if (!phone.trim()) return;
    setError("");
    setStep("sending");
    try {
      await sendWorkerCode(phone.trim());
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
        phone.trim(),
        code.trim(),
        twoFaPassword,
      );
      if (result.status === "2fa_required") {
        setStep("2fa");
        return;
      }
      setStep("done");
      setPhone("");
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
              <div
                key={w.id}
                className="flex items-center justify-between py-2 px-3 rounded-lg bg-[#27272a]/50"
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
              </div>
            ))}
          </div>
        )}

        {/* Add worker form */}
        {step === "done" ? (
          <p className="text-green-400 text-sm text-center py-2">
            Worker aggiunto con successo!
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {/* Phone input (always visible when not done) */}
            <div className="flex gap-2">
              <input
                type="tel"
                placeholder="+39 123 456 7890"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                onKeyDown={(e) => handleKeyDown(e, handleSendCode)}
                disabled={step !== "idle" && step !== "sending"}
                className="flex-1 h-9 px-3 rounded-lg bg-[#27272a] border border-[#3f3f46] text-[#fafafa] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#e5a00d] disabled:opacity-50"
              />
              {step === "idle" && (
                <button
                  onClick={handleSendCode}
                  disabled={!phone.trim()}
                  className="h-9 px-3 rounded-lg bg-[#e5a00d] text-black text-sm font-medium hover:bg-[#c98b0b] transition-colors disabled:opacity-50 flex items-center gap-1.5"
                >
                  <Plus className="w-4 h-4" />
                  Invia codice
                </button>
              )}
              {step === "sending" && (
                <div className="h-9 px-3 flex items-center">
                  <Loader2 className="w-4 h-4 text-[#e5a00d] animate-spin" />
                </div>
              )}
            </div>

            {/* Code input */}
            {(step === "code" || step === "verifying") && (
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Codice di verifica"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  onKeyDown={(e) => handleKeyDown(e, () => handleVerifyCode())}
                  disabled={step === "verifying"}
                  className="flex-1 h-9 px-3 rounded-lg bg-[#27272a] border border-[#3f3f46] text-[#fafafa] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#e5a00d] disabled:opacity-50"
                  autoFocus
                />
                <button
                  onClick={() => handleVerifyCode()}
                  disabled={!code.trim() || step === "verifying"}
                  className="h-9 px-3 rounded-lg bg-[#e5a00d] text-black text-sm font-medium hover:bg-[#c98b0b] transition-colors disabled:opacity-50"
                >
                  {step === "verifying" ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    "Verifica"
                  )}
                </button>
              </div>
            )}

            {/* 2FA password input */}
            {step === "2fa" && (
              <div className="flex flex-col gap-2">
                <p className="text-xs text-[#a1a1aa]">
                  Account con verifica in due passaggi (2FA)
                </p>
                <div className="flex gap-2">
                  <input
                    type="password"
                    placeholder="Password 2FA"
                    value={password2fa}
                    onChange={(e) => setPassword2fa(e.target.value)}
                    onKeyDown={(e) =>
                      handleKeyDown(e, () => handleVerifyCode(password2fa))
                    }
                    className="flex-1 h-9 px-3 rounded-lg bg-[#27272a] border border-[#3f3f46] text-[#fafafa] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#e5a00d]"
                    autoFocus
                  />
                  <button
                    onClick={() => handleVerifyCode(password2fa)}
                    disabled={!password2fa.trim()}
                    className="h-9 px-3 rounded-lg bg-[#e5a00d] text-black text-sm font-medium hover:bg-[#c98b0b] transition-colors disabled:opacity-50"
                  >
                    Conferma
                  </button>
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
