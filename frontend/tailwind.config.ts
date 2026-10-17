import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ivory: {
          DEFAULT: "#FAF6F0",
          card: "#F3EDE2",
          deep: "#E8DFD1",
        },
        ink: {
          DEFAULT: "#141413",
          muted: "#4A4843",
          subtle: "#78746C",
        },
        vermilion: {
          DEFAULT: "#C83E2B",
          dark: "#A32E1E",
          light: "#FDF2F0",
        },
        poleA: {
          DEFAULT: "#1D4ED8",
          bg: "#EFF6FF",
          border: "#BFDBFE",
        },
        mixedPole: {
          DEFAULT: "#B45309",
          bg: "#FEF3C7",
          border: "#FDE68A",
        },
        poleB: {
          DEFAULT: "#0F766E",
          bg: "#F0FDFA",
          border: "#99F6E4",
        },
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "Cambria", "Times New Roman", "serif"],
        sans: ["var(--font-sans)", "system-ui", "-apple-system", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
