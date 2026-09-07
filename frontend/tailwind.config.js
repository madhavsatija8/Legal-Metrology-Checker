/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // "Case file" palette: warm ledger paper + ink, with a stamp-red
        // accent reserved for violations and a steel-blue for actions.
        // Deliberately not the cream/terracotta SaaS default.
        paper: "#EAE6DA",
        "paper-raised": "#F2EFE5",
        ink: "#1E2A30",
        "ink-soft": "#4B5560",
        rule: "#C3BBA6",
        seal: "#A6392B",
        "seal-soft": "#F1DAD3",
        verified: "#3D6B4F",
        "verified-soft": "#DCE7DD",
        caution: "#9C6A16",
        "caution-soft": "#F0E3C9",
        action: "#2B5876",
        "action-soft": "#DCE7EC",
      },
      fontFamily: {
        serif: ["'Source Serif 4'", "Georgia", "serif"],
        sans: ["'IBM Plex Sans'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
