import type { SVGProps } from "react";

import type { FindingCategory } from "@/lib/api/types";

/** Inline SVG keeps icons theme-aware (currentColor) and adds no dependency. */
const base: SVGProps<SVGSVGElement> = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
  focusable: false,
};

export const PulseIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M2 12h4l2.5-7 5 14L16 12h6" />
  </svg>
);

export const HistoryIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M3 12a9 9 0 1 0 2.6-6.4M3 4v4h4" />
    <path d="M12 7v5l3 2" />
  </svg>
);

export const SymptomIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M12 20s-7-4.4-7-9a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 4.6-7 9-7 9Z" />
  </svg>
);

export const ExamIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M6 3v6a4 4 0 0 0 8 0V3" />
    <path d="M4 3h3M13 3h3" />
    <path d="M10 13v2a5 5 0 0 0 10 0v-1" />
    <circle cx="20" cy="11" r="2" />
  </svg>
);

export const LabIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M9 3v6.5L4.5 17A2 2 0 0 0 6.3 20h11.4a2 2 0 0 0 1.8-3L15 9.5V3" />
    <path d="M8 3h8M7.5 14h9" />
  </svg>
);

export const ImagingIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <rect x="3" y="3" width="18" height="18" rx="3" />
    <path d="M8 3v18M16 3v18M3 9h18M3 15h18" />
  </svg>
);

export const NoteIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M5 3h10l4 4v14H5z" />
    <path d="M15 3v4h4M9 12h6M9 16h4" />
  </svg>
);

export const UserIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="8" r="3.5" />
    <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
  </svg>
);

export const StethoscopeIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M6 3v5a4 4 0 0 0 8 0V3" />
    <path d="M4 3h3M13 3h3" />
    <path d="M10 12v3a5 5 0 0 0 10 0v-2" />
    <circle cx="20" cy="11" r="2" />
  </svg>
);

export const ArrowRightIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

export const ArrowLeftIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M19 12H5M11 18l-6-6 6-6" />
  </svg>
);

export const CheckIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M20 6 9 17l-5-5" />
  </svg>
);

export const PartialIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" stroke="none" />
  </svg>
);

export const CrossIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
);

export const AlertIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M12 3 2.5 19.5h19z" />
    <path d="M12 9v4.5M12 17h.01" />
  </svg>
);

export const InboxIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M3 13h5l1.5 3h5L16 13h5" />
    <path d="M5.5 5h13l2.5 8v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5z" />
  </svg>
);

export const CATEGORY_ICON: Record<
  FindingCategory,
  (p: SVGProps<SVGSVGElement>) => React.JSX.Element
> = {
  history: HistoryIcon,
  symptom: SymptomIcon,
  vital_sign: PulseIcon,
  physical_exam: ExamIcon,
  laboratory: LabIcon,
  imaging: ImagingIcon,
  other: NoteIcon,
};

export const SunIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);

export const MoonIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}>
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
  </svg>
);
