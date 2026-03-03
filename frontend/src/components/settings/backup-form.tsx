"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSButton, DSCard, DSInput } from "@/components/ds";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface BackupFormProps {
  channelIds: number[];
  mainChannelId: string;
  onMainChannelIdChange: (v: string) => void;
  backupTitle: string;
  onBackupTitleChange: (v: string) => void;
  inviteMembers: boolean;
  onInviteMembersChange: (v: boolean) => void;
  creating: boolean;
  onCreate: () => void;
  onCancel: () => void;
}

export function BackupForm({
  channelIds,
  mainChannelId,
  onMainChannelIdChange,
  backupTitle,
  onBackupTitleChange,
  inviteMembers,
  onInviteMembersChange,
  creating,
  onCreate,
  onCancel,
}: BackupFormProps) {
  const t = useTranslations("backup");
  const tc = useTranslations("common");

  return (
    <DSCard
      level="secondary"
      className="p-3 rounded-lg shadow-none backdrop-blur-none gap-3"
    >
      {channelIds.length > 1 ? (
        <Select value={mainChannelId} onValueChange={onMainChannelIdChange}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder={t("mainChannelId")} />
          </SelectTrigger>
          <SelectContent>
            {channelIds.map((id) => (
              <SelectItem key={id} value={String(id)}>
                {id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (
        <div className="h-9 px-3 rounded-lg bg-[#27272a] border border-[#3f3f46] text-[#fafafa] text-sm flex items-center">
          {mainChannelId || t("mainChannelId")}
        </div>
      )}

      <DSInput
        placeholder={t("backupTitle")}
        value={backupTitle}
        onChange={(e) => onBackupTitleChange(e.target.value)}
      />

      <div className="flex items-center justify-between">
        <label className="text-xs text-[#a1a1aa]">{t("inviteMembers")}</label>
        <Switch
          checked={inviteMembers}
          onCheckedChange={onInviteMembersChange}
        />
      </div>

      <div className="flex gap-2">
        <DSButton variant="secondary" onClick={onCancel} className="flex-1">
          {tc("cancel")}
        </DSButton>
        <DSButton
          variant="primary"
          onClick={onCreate}
          disabled={creating || !mainChannelId || !backupTitle.trim()}
          className="flex-1"
          icon={
            creating ? <Loader2 className="w-4 h-4 animate-spin" /> : undefined
          }
        >
          {creating ? t("creating") : t("create")}
        </DSButton>
      </div>
    </DSCard>
  );
}
