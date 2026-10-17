import type { Config } from "tailwindcss";

/**
 * Beyond Style design tokens.
 *
 * Palette comes from the brand boards the owner supplied (gold / black /
 * cream / deep blue / sand — see docs/reference/owner-samples/README.md and
 * app/data/product_catalogue.json#packaging). Everything else (radii,
 * shadows, motion) is defined once here and consumed by components/ui.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          // Legacy aliases kept so untouched screens keep rendering.
          gold: "#B08D3E",
          dark: "#1C1917",
          cream: "#FAF7F1",
        },
        gold: {
          50: "#FBF6EA",
          100: "#F3E8C8",
          200: "#E6D199",
          300: "#D4B55F",
          400: "#C39F48",
          500: "#B08D3E",
          600: "#8F7030",
          700: "#6E5523",
          800: "#4D3B18",
        },
        ink: {
          DEFAULT: "#141210",
          900: "#141210",
          800: "#1C1917",
          700: "#2A2622",
          600: "#4A443E",
          500: "#6B645C",
          400: "#8E867D",
          300: "#B6AEA4",
          200: "#D8D2C8",
          100: "#EDE8DF",
        },
        cream: {
          DEFAULT: "#FAF7F1",
          50: "#FDFBF7",
          100: "#FAF7F1",
          200: "#F4EEE2",
          300: "#EAE1D0",
        },
        sand: {
          DEFAULT: "#C9B48C",
          100: "#EFE6D3",
          200: "#E2D4B5",
          300: "#D9C7A3",
          400: "#C9B48C",
          500: "#B39B6E",
        },
        navy: {
          DEFAULT: "#1B2A4A",
          500: "#233A66",
          600: "#1B2A4A",
          700: "#13203A",
        },
        ok: { 50: "#ECFDF3", 600: "#15803D", 800: "#166534" },
        warn: { 50: "#FFF8E6", 600: "#B45309", 800: "#92400E" },
        danger: { 50: "#FEF2F2", 600: "#B91C1C", 800: "#991B1B" },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Tahoma", "Arial", "sans-serif"],
        display: ["var(--font-display)", "Georgia", "serif"],
        serif: ["var(--font-display)", "Georgia", "serif"],
      },
      borderRadius: {
        xl: "1rem",
        "2xl": "1.25rem",
        "3xl": "1.75rem",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(20,18,16,0.05), 0 10px 30px -16px rgba(20,18,16,0.22)",
        lift: "0 2px 4px rgba(20,18,16,0.06), 0 18px 40px -18px rgba(20,18,16,0.30)",
        gold: "0 10px 30px -14px rgba(176,141,62,0.55)",
      },
      transitionTimingFunction: {
        "out-soft": "cubic-bezier(0.2, 0.8, 0.2, 1)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        "fade-up": "fade-up 220ms cubic-bezier(0.2, 0.8, 0.2, 1) both",
        shimmer: "shimmer 1.6s linear infinite",
      },
    },
  },
  plugins: [],
};
export default config;
