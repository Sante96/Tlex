"use client";

import { useState } from "react";
import { Users, Shield, ShieldOff, Trash2, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSButton, DSCard } from "@/components/ds";
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
  const t = useTranslations();

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
        `${t("users.deleteConfirm")} ${user.email}? ${t("profiles.edit.deleteWarning")}`,
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

  const description = `${users.length} ${users.length === 1 ? t("users.registeredOne") : t("users.registeredMany")}`;

  return (
    <DSCard
      icon={<Users className="w-5 h-5 text-[#e5a00d]" />}
      title={t("users.title")}
      description={description}
    >
      <div className="flex justify-end -mt-1">
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
            <DSCard
              key={user.id}
              level="secondary"
              className="p-3 rounded-lg shadow-none backdrop-blur-none flex-row items-center justify-between gap-0"
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
                      <span className="ml-2 text-xs text-[#71717a]">
                        ({t("users.you")})
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-[#71717a]">
                    {user.profiles_count}{" "}
                    {user.profiles_count === 1
                      ? t("users.profileOne")
                      : t("users.profileMany")}
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
                    title={t("users.deleteUser")}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </DSCard>
          );
        })}
      </div>
    </DSCard>
  );
}
