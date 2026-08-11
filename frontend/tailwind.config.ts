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
        bg: "var(--bg)",
        "bg-ring": "var(--bg-ring)",
        surface: "var(--surface)",
        card: "var(--card)",
        "card-2": "var(--card-2)",
        border: "var(--border)",
        text: "var(--text)",
        muted: "var(--muted)",
        "muted-2": "var(--muted-2)",
        calm: "var(--calm)",
        mid: "var(--mid)",
        crisis: "var(--crisis)",
        accent: "var(--accent)",
        shadow: "var(--shadow)",
      },
      fontFamily: {
        kr: ["var(--font-noto-sans-kr)", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"],
      },
      boxShadow: {
        card: "0 8px 24px -12px var(--shadow)",
      },
    },
  },
  plugins: [],
};
export default config;
