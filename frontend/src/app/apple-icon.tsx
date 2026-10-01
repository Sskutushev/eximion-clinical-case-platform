import { ImageResponse } from "next/og";

// iOS ignores SVG touch icons, so this one is rendered to PNG at build time.
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #38bdf8 0%, #7c3aed 100%)",
        }}
      >
        <svg
          width="112"
          height="112"
          viewBox="0 0 64 64"
          fill="none"
          stroke="#fff"
          strokeWidth="4.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M20 14v12a9 9 0 0 0 18 0V14" />
          <path d="M16 14h7M35 14h7" />
          <path d="M29 35v5a10 10 0 0 0 20 0v-3" />
          <circle cx="49" cy="29" r="5" />
        </svg>
      </div>
    ),
    size,
  );
}
