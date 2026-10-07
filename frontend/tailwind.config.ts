import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: { DEFAULT: "#0f1419", card: "#1a2332", border: "#2d3a4f" },
        accent: { DEFAULT: "#3b82f6", muted: "#64748b" },
      },
    },
  },
  plugins: [],
};
export default config;
