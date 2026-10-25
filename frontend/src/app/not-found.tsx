import Link from "next/link";
import { getTranslations } from "next-intl/server";

// Unknown addresses: Next's default page had nothing a D-pad could focus
export default async function NotFound() {
  const t = await getTranslations();
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-4 px-4 bg-[#09090b] text-center">
      <h1 className="text-2xl font-bold text-[#fafafa]">{t("errors.notFoundTitle")}</h1>
      <p className="text-[#a1a1aa]">{t("errors.notFoundText")}</p>
      <Link
        href="/"
        autoFocus
        className="mt-2 h-11 px-6 inline-flex items-center rounded-[10px] bg-[#e5a00d] text-black font-semibold outline-none focus-visible:ring-2 focus-visible:ring-[#e5a00d] focus-visible:ring-offset-2 focus-visible:ring-offset-[#09090b]"
      >
        {t("nav.home")}
      </Link>
    </main>
  );
}
