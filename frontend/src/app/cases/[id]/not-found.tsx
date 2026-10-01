import Link from "next/link";

import { ArrowLeftIcon, InboxIcon } from "@/components/icons";
import { getTranslations } from "@/i18n/server";

export default async function CaseNotFound() {
  const { t } = await getTranslations();

  return (
    <div className="panel empty">
      <InboxIcon />
      <div>
        <h1 className="page-title" style={{ fontSize: "1.5rem" }}>
          {t.case.notFoundTitle}
        </h1>
        <p className="hint" style={{ marginTop: "0.5rem" }}>
          {t.case.notFoundBody}
        </p>
      </div>
      <Link href="/" className="btn btn--ghost">
        <ArrowLeftIcon />
        {t.nav.back}
      </Link>
    </div>
  );
}
