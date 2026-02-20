/* ── Shared: Field wrapper for edit modal forms ──────────────── */
export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-[#a1a1aa] uppercase tracking-wide">
        {label}
      </label>
      {children}
    </div>
  );
}
