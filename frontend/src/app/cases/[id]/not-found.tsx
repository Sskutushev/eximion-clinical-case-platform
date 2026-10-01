import Link from "next/link";

import { ArrowLeftIcon, InboxIcon } from "@/components/icons";

export default function CaseNotFound() {
  return (
    <div className="panel empty">
      <InboxIcon />
      <div>
        <h1 className="page-title" style={{ fontSize: "1.5rem" }}>
          Case not found
        </h1>
        <p className="hint" style={{ marginTop: "0.5rem" }}>
          This case does not exist, or it is no longer available.
        </p>
      </div>
      <Link href="/" className="btn btn--ghost">
        <ArrowLeftIcon />
        Back to all cases
      </Link>
    </div>
  );
}
