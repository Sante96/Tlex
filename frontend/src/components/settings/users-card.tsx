"use client";

import { useState } from "react";
import { Users, Shield, ShieldOff, Trash2, RefreshCw } from "lucide-react";
import { DSButton } from "@/components/ds";
import { Switch } from "@/components/ui/switch";
import { toggleUserAdmin, deleteUser, type UserInfo } from "@/lib/api";

interface UsersCardProps {
  users: UserInfo[];
  currentUserId: number;
  loading: boolean;
  onRefresh: () => void;
}

export function UsersCard({
  users,
  currentUserId,
  loading,
  onRefresh,
}: UsersCardProps) {
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const handleToggleAdmin = async (userId: number, newValue: boolean) => {
    setTogglingId(userId);
    try {
      await toggleUserAdmin(userId, newValue);
      onRefresh();
    } catch {}
    setTogglingId(null);
  };

  const handleDelete = async (user: UserInfo) => {
    if (
      !window.confirm(
        `Eliminare l'utente ${user.email}? Questa azione è irreversibile.`,
      )
    )
      return;
    setDeletingId(user.id);
    try {
      await deleteUser(user.id);
      onRefresh();
    } catch {}
    setDeletingId(null);
  };

  return (
    <div className="bg-zinc-900 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Users className="w-5 h-5 text-[#e5a00d]" />
          <div>
            <h2 className="font-semibold text-[#fafafa]">Utenti</h2>
            <p className="text-xs text-[#71717a]">
              {users.length}{" "}
              {users.length === 1 ? "utente registrato" : "utenti registrati"}
            </p>
          </div>
        </div>
        <DSButton
          variant="ghost"
          onClick={onRefresh}
          disabled={loading}
          className="!h-8 !w-8 !px-0"
          icon={
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          }
        />
      </div>

      <div className="space-y-2">
        {users.map((user) => {
          const isSelf = user.id === currentUserId;
          return (
            <div
              key={user.id}
              className="flex items-center justify-between bg-zinc-800 rounded-lg p-3"
            >
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <div
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    user.is_admin ? "bg-[#e5a00d]" : "bg-[#3f3f46]"
                  }`}
                />
                <div className="min-w-0">
                  <div className="text-sm font-medium text-[#fafafa] truncate">
                    {user.email}
                    {isSelf && (
                      <span className="ml-2 text-xs text-[#71717a]">(tu)</span>
                    )}
                  </div>
                  <div className="text-xs text-[#71717a]">
                    {user.profiles_count}{" "}
                    {user.profiles_count === 1 ? "profilo" : "profili"}
                    {user.profiles.length > 0 && (
                      <span className="ml-1">
                        · {user.profiles.map((p) => p.name).join(", ")}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                {/* Admin toggle */}
                <div className="flex items-center gap-2">
                  {user.is_admin ? (
                    <Shield className="w-3.5 h-3.5 text-[#e5a00d]" />
                  ) : (
                    <ShieldOff className="w-3.5 h-3.5 text-[#52525b]" />
                  )}
                  <Switch
                    checked={user.is_admin}
                    disabled={isSelf || togglingId === user.id}
                    onCheckedChange={(checked: boolean) =>
                      handleToggleAdmin(user.id, checked)
                    }
                  />
                </div>

                {/* Delete button */}
                {!isSelf && (
                  <button
                    onClick={() => handleDelete(user)}
                    disabled={deletingId === user.id}
                    className="p-1.5 rounded-md transition-colors text-[#52525b] hover:text-red-400 hover:bg-red-500/10"
                    title="Elimina utente"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
