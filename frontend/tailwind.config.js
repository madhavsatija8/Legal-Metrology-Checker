/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Token names kept identical to the previous "case file" theme on
        // purpose: every page/table in this app already references
        // bg-paper, text-ink, border-rule, etc. Re-pointing the tokens at
        // a modern product palette re-skins the whole app without having
        // to touch every page file.
        paper: "#F4F5FA", // app canvas — soft indigo-tinted gray, not white-on-white
        "paper-raised": "#FFFFFF", // cards/panels sit on true white for lift
        ink: "#161B33",
        "ink-soft": "#6B7195",
        rule: "#E4E6F2",
        seal: "#DC2626",
        "seal-soft": "#FEE2E2",
        verified: "#059669",
        "verified-soft": "#D1FAE5",
        caution: "#D97706",
        "caution-soft": "#FEF3C7",
        action: "#4F46E5",
        "action-soft": "#EEF2FF",
        sidebar: "#161B33",
        "sidebar-hover": "#232A52",
      },
      fontFamily: {
        serif: ["'Plus Jakarta Sans'", "system-ui", "sans-serif"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
      },
      borderRadius: {
        xl2: "1rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(22, 27, 51, 0.04), 0 1px 8px rgba(22, 27, 51, 0.06)",
        raised: "0 4px 16px rgba(22, 27, 51, 0.08), 0 1px 3px rgba(22, 27, 51, 0.06)",
        pop: "0 12px 32px rgba(22, 27, 51, 0.14)",
      },
    },
  },
  plugins: [],
};
