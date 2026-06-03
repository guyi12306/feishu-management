import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{vue,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 深海青金 · 主品牌
        brand: {
          50:  "#EEF1FE",
          100: "#DEE5FC",
          200: "#BFCBF9",
          300: "#94A4F1",
          400: "#6979E8",
          500: "#4F46E5",   // 主 CTA
          600: "#3F37C9",
          700: "#332CA3",
          800: "#272283",
          900: "#1B1762",
        },
        // 点缀暗金
        gold: {
          50:  "#FBF4E6",
          100: "#F4E2BE",
          200: "#E8C886",
          300: "#DDB05A",
          400: "#D4A056",
          500: "#B7853A",   // 暗金主调
          600: "#8E6428",
        },
        // 文字
        ink: {
          900: "#0F1419",
          700: "#374151",
          500: "#6B7280",
          400: "#9CA3AF",
          300: "#D1D5DB",
        },
        // 状态
        success: "#10B981",
        danger:  "#EF4444",
        // 玻璃面背景候选
        glass: {
          DEFAULT: "rgba(255,255,255,0.55)",
          strong:  "rgba(255,255,255,0.65)",
          flat:    "rgba(255,255,255,0.70)",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system", "BlinkMacSystemFont",
          "PingFang SC", "Microsoft YaHei",
          "Segoe UI", "Helvetica Neue",
          "sans-serif",
        ],
      },
      fontSize: {
        display: ["30px", { lineHeight: "1.2",  letterSpacing: "-0.02em", fontWeight: "600" }],
        title:   ["19px", { lineHeight: "1.35", letterSpacing: "-0.01em", fontWeight: "600" }],
        body:    ["14.5px", { lineHeight: "1.55" }],
        caption: ["12.5px", { lineHeight: "1.5" }],
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "20px",
      },
      boxShadow: {
        glass: "0 8px 32px rgba(15, 20, 25, 0.04)",
        "glass-strong": "0 24px 48px rgba(15, 20, 25, 0.08)",
        "inset-hi": "inset 0 1px 0 rgba(255,255,255,0.6)",
        "inset-hi-strong": "inset 0 1px 0 rgba(255,255,255,0.8)",
      },
      backdropBlur: {
        glass: "24px",
        strong: "32px",
      },
      backdropSaturate: {
        glass: "180%",
      },
      transitionTimingFunction: {
        "out-quart": "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      keyframes: {
        "fade-in":   { from: { opacity: "0" }, to: { opacity: "1" } },
        "rise":      { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
      animation: {
        "fade-in": "fade-in 0.25s cubic-bezier(0.4, 0, 0.2, 1) both",
        "rise":    "rise 0.3s cubic-bezier(0.4, 0, 0.2, 1) both",
      },
    },
  },
  plugins: [],
} satisfies Config;
