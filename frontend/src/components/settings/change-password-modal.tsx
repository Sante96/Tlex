"use client";

import { useState } from "react";
import { X, Eye, EyeOff, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSButton, DSIconButton, DSInput } from "@/components/ds";
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
          <h2 className="text-xl font-semibold text-white">
            {t("changePassword.title")}
          </h2>
          <DSIconButton
            onClick={onClose}
            className="hover:text-white text-white/50"
            icon={<X className="h-5 w-5" />}
          />
        </div>

        {success ? (
          <p className="text-green-400 text-center py-4">
            {t("changePassword.success")}
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <DSInput
              label={t("changePassword.current")}
              type={showCurrent ? "text" : "password"}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              suffix={
                <button
                  type="button"
                  onClick={() => setShowCurrent(!showCurrent)}
                  className="text-[#71717a] hover:text-[#fafafa] transition-colors"
                >
                  {showCurrent ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              }
            />
            <DSInput
              label={t("changePassword.new")}
              type={showNew ? "text" : "password"}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={6}
              suffix={
                <button
                  type="button"
                  onClick={() => setShowNew(!showNew)}
                  className="text-[#71717a] hover:text-[#fafafa] transition-colors"
                >
                  {showNew ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              }
            />
            <DSInput
              label={t("changePassword.confirm")}
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={6}
            />

            {error && (
              <p className="text-red-400 text-sm text-center">{error}</p>
            )}

            <div className="flex items-center justify-end gap-3 pt-1">
              <DSButton type="button" variant="ghost" onClick={onClose}>
                {t("common.cancel")}
              </DSButton>
              <DSButton
                type="submit"
                disabled={loading}
                icon={
                  loading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : undefined
                }
              >
                {loading
                  ? t("changePassword.saving")
                  : t("changePassword.submit")}
              </DSButton>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
