/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#070B14",
        surface: "#0F172A",
        card: "#111827",
        "card-hover": "#1a2235",
        accent: {
          DEFAULT: "#7C3AED",
          light: "#9D5FF5",
          dark: "#5B21B6",
        },
        cyber: {
          purple: "#7C3AED",
          blue: "#3B82F6",
          cyan: "#06B6D4",
          pink: "#EC4899",
          green: "#10B981",
        },
        success: "#10B981",
        warning: "#F59E0B",
        error: "#EF4444",
        "text-primary": "#F8FAFC",
        "text-secondary": "#94A3B8",
        "text-muted": "#475569",
        border: "rgba(255,255,255,0.06)",
        "border-accent": "rgba(124,58,237,0.4)",
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-cyber":
          "linear-gradient(135deg, #7C3AED 0%, #3B82F6 50%, #06B6D4 100%)",
        "gradient-glow":
          "linear-gradient(180deg, rgba(124,58,237,0.15) 0%, transparent 100%)",
        "grid-pattern":
          "linear-gradient(rgba(124,58,237,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(124,58,237,0.05) 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "40px 40px",
      },
      boxShadow: {
        glow: "0 0 20px rgba(124,58,237,0.4)",
        "glow-sm": "0 0 10px rgba(124,58,237,0.3)",
        "glow-cyan": "0 0 20px rgba(6,182,212,0.4)",
        "glow-green": "0 0 20px rgba(16,185,129,0.4)",
        card: "0 4px 24px rgba(0,0,0,0.4)",
        "card-hover": "0 8px 40px rgba(0,0,0,0.6), 0 0 20px rgba(124,58,237,0.1)",
        inner: "inset 0 1px 0 rgba(255,255,255,0.05)",
      },
      animation: {
        "pulse-slow": "pulse 3s ease-in-out infinite",
        "spin-slow": "spin 4s linear infinite",
        shimmer: "shimmer 2s linear infinite",
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.4s ease-out",
        "slide-right": "slideRight 0.3s ease-out",
        flicker: "flicker 0.15s ease-in-out",
        "scan-line": "scanLine 3s linear infinite",
        "glow-pulse": "glowPulse 2s ease-in-out infinite",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        fadeIn: {
          "0%": { opacity: 0 },
          "100%": { opacity: 1 },
        },
        slideUp: {
          "0%": { opacity: 0, transform: "translateY(10px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
        slideRight: {
          "0%": { opacity: 0, transform: "translateX(-10px)" },
          "100%": { opacity: 1, transform: "translateX(0)" },
        },
        flicker: {
          "0%, 100%": { opacity: 1 },
          "50%": { opacity: 0.8 },
        },
        scanLine: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        glowPulse: {
          "0%, 100%": { boxShadow: "0 0 10px rgba(124,58,237,0.3)" },
          "50%": { boxShadow: "0 0 25px rgba(124,58,237,0.6), 0 0 50px rgba(124,58,237,0.2)" },
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      borderRadius: {
        xl: "0.75rem",
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
    },
  },
  plugins: [],
};
