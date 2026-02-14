interface SettingsCardProps {
  icon: React.ElementType;
  title: string;
  description?: string;
  children: React.ReactNode;
}

export function SettingsCard({
  icon: Icon,
  title,
  description,
  children,
}: SettingsCardProps) {
  return (
    <div
      className="rounded-xl p-6 flex flex-col gap-4"
      style={{ backgroundColor: "#18181b" }}
    >
      <div className="flex items-center gap-3">
        <Icon className="w-5 h-5 text-[#e5a00d]" />
        <div>
          <h2 className="font-semibold text-[#fafafa]">{title}</h2>
          {description && (
            <p className="text-xs text-[#71717a]">{description}</p>
          )}
        </div>
      </div>
      {children}
    </div>
  );
}
