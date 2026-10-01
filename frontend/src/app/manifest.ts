import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Eximion Clinical Cases",
    short_name: "Eximion",
    description: "Solve clinical cases and get an instant, explainable score.",
    start_url: "/",
    display: "standalone",
    background_color: "#080b16",
    theme_color: "#080b16",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/apple-icon", sizes: "180x180", type: "image/png" },
    ],
  };
}
