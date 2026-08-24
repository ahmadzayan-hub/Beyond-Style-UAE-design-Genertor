import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          gold: "#b08d3e",
          dark: "#1c1917",
          cream: "#faf7f1",
        },
      },
    },
  },
  plugins: [],
};
export default config;
