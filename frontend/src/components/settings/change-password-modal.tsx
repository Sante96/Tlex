"use client";

import { useState } from "react";
import { X, Eye, EyeOff } from "lucide-react";
import { useTranslations } from "next-intl";
import { changePassword } from "@/lib/api";
import { AxiosError } from "axios";

interface ChangePasswordModalProps {
  onClose: () => void;
}

export function ChangePasswordModal({ onClose }: ChangePasswordModalProps) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const t = useTranslations();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (newPassword.length < 6) {
      setError(t("changePassword.errorGeneral"));
      return;
    }

    if (newPassword !== confirmPassword) {
      setError(t("changePassword.errorMismatch"));
      return;
    }

    setLoading(true);
    try {
      await changePassword(currentPassword, newPassword);
      setSuccess(true);
      setTimeout(onClose, 1500);
    } catch (err) {
      if (err instanceof AxiosError && err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (detail === "Current password is incorrect") {
          setError(t("changePassword.errorGeneral"));
        } else {
          setError(detail);
        }
      } else {
        setError(t("changePassword.errorGeneral"));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div
        className="rounded-xl p-6 max-w-sm w-full shadow-[0_8px_32px_rgba(0,0,0,0.5)]"
        style={{
          backgroundColor: "rgba(10,10,10,0.75)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div className="flex justify-between items-start mb-6">
          <h2 className="text-xl font-semibold text-white">{t("changePassword.title")}</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 transition-colors text-white/50 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {success ? (
          <p className="text-green-400 text-center py-4">
            {t("changePassword.success")}
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-white/70">{t("changePassword.current")}</label>
              <div className="relative">
                <input
                  type={showCurrent ? "text" : "password"}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full h-10 px-3 pr-10 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-[#e5a00d] transition-colors"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent(!showCurrent)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/80 transition-colors"
                >
                  {showCurrent ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-white/70">{t("changePassword.new")}</label>
              <div className="relative">
                <input
                  type={showNew ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full h-10 px-3 pr-10 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-[#e5a00d] transition-colors"
                  required
                  minLength={6}
                />
                <button
                  type="button"
                  onClick={() => setShowNew(!showNew)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/80 transition-colors"
                >
                  {showNew ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-white/70">{t("changePassword.confirm")}</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full h-10 px-3 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-[#e5a00d] transition-colors"
                required
                minLength={6}
              />
            </div>

            {error && (
              <p className="text-red-400 text-sm text-center">{error}</p>
            )}

            <div className="flex items-center justify-end gap-3 pt-1">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-lg text-sm font-medium text-white/70 hover:bg-white/[0.08] transition-colors"
              >
                {t("common.cancel")}
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-5 py-2 rounded-lg text-sm font-semibold text-black bg-[#e5a00d] hover:bg-[#f0b429] transition-colors disabled:opacity-50"
              >
                {loading ? t("changePassword.saving") : t("changePassword.submit")}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
