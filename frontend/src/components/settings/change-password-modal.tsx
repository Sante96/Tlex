"use client";

import { useState } from "react";
import { X, Eye, EyeOff } from "lucide-react";
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (newPassword.length < 6) {
      setError("La nuova password deve avere almeno 6 caratteri");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("Le password non coincidono");
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
          setError("La password attuale non è corretta");
        } else {
          setError(detail);
        }
      } else {
        setError("Errore nel cambio password");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-zinc-900 rounded-xl p-6 max-w-sm w-full border border-zinc-800">
        <div className="flex justify-between items-start mb-6">
          <h2 className="text-xl font-semibold text-white">Cambia password</h2>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {success ? (
          <p className="text-green-400 text-center py-4">
            Password cambiata con successo!
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-zinc-400">Password attuale</label>
              <div className="relative">
                <input
                  type={showCurrent ? "text" : "password"}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full h-10 px-3 pr-10 rounded-lg bg-zinc-800 border border-zinc-700 text-white text-sm focus:outline-none focus:border-[#e5a00d]"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent(!showCurrent)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white"
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
              <label className="text-sm text-zinc-400">Nuova password</label>
              <div className="relative">
                <input
                  type={showNew ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full h-10 px-3 pr-10 rounded-lg bg-zinc-800 border border-zinc-700 text-white text-sm focus:outline-none focus:border-[#e5a00d]"
                  required
                  minLength={6}
                />
                <button
                  type="button"
                  onClick={() => setShowNew(!showNew)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white"
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
              <label className="text-sm text-zinc-400">Conferma password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full h-10 px-3 rounded-lg bg-zinc-800 border border-zinc-700 text-white text-sm focus:outline-none focus:border-[#e5a00d]"
                required
                minLength={6}
              />
            </div>

            {error && (
              <p className="text-red-500 text-sm text-center">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="h-10 rounded-lg bg-[#e5a00d] text-black font-medium text-sm hover:bg-[#c98b0b] transition-colors disabled:opacity-50"
            >
              {loading ? "Salvataggio..." : "Cambia password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
