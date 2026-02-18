/**
 * Copyright AGNTCY Contributors (https://github.com/agntcy)
 * SPDX-License-Identifier: Apache-2.0
 **/

import tailwindcssAnimate from "tailwindcss-animate"

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        "app-background": "var(--app-background)",

        "node-background": "var(--node-background)",
        "node-data-background": "var(--node-data-background)",
        "node-background-hover": "var(--node-background-hover)",
        "node-background-active": "var(--node-background-active)",
        "node-text-primary": "var(--node-text-primary)",
        "node-text-secondary": "var(--node-text-secondary)",
        "node-icon-background": "var(--node-icon-background)",

        "edge-label-background": "var(--edge-label-background)",
        "edge-label-background-active": "var(--edge-label-background-active)",
        "edge-label-text": "var(--edge-label-text)",
        "edge-label-text-active": "var(--edge-label-text-active)",

        "accent-primary": "var(--accent-primary)",
        "accent-border": "var(--accent-border)",

        "nav-background": "var(--nav-background)",
        "nav-background-secondary": "var(--nav-background-secondary)",
        "nav-border": "var(--nav-border)",
        "nav-text": "var(--nav-text)",

        "chat-background": "var(--chat-background)",
        "chat-background-hover": "var(--chat-background-hover)",
        "chat-text": "var(--chat-text)",
        "chat-input-background": "var(--chat-input-background)",
        "chat-input-border": "var(--chat-input-border)",
        "chat-dropdown-background": "var(--chat-dropdown-background)",
        "chat-dropdown-icon": "var(--chat-dropdown-icon)",

        "action-background": "var(--action-background)",
        "action-background-hover": "var(--action-background-hover)",

        "sidebar-background": "var(--sidebar-background)",
        "sidebar-item-selected": "var(--sidebar-item-selected)",
        "sidebar-border": "var(--sidebar-border)",
        "sidebar-text": "var(--sidebar-text)",

        "shadow-default": "var(--shadow-default)",
        "overlay-background": "var(--overlay-background)",
        "control-border-weak": "var(--control-border-weak)",

        "modal-background": "var(--modal-background)",
        "modal-border": "var(--modal-border)",
        "modal-text": "var(--modal-text)",
        "modal-text-secondary": "var(--modal-text-secondary)",
        "modal-accent": "var(--modal-accent)",
        "modal-hover": "var(--modal-hover)",
        "modal-button": "var(--modal-button)",
        "modal-button-text": "var(--modal-button-text)",
        "modal-button-hover": "var(--modal-button-hover)",

        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        chart: {
          1: "hsl(var(--chart-1))",
          2: "hsl(var(--chart-2))",
          3: "hsl(var(--chart-3))",
          4: "hsl(var(--chart-4))",
          5: "hsl(var(--chart-5))",
        },
      },
      borderColor: {
        "sidebar-border": "var(--sidebar-border)",
        "nav-border": "var(--nav-border)",
        "modal-border": "var(--modal-border)",
        "accent-border": "var(--accent-border)",
      },
      spacing: {
        122: "122px",
        160: "160px",
        162: "162px",
        166: "166px",
        194: "194px",
        269: "269px",
      },
      width: {
        122: "122px",
        160: "160px",
        162: "162px",
        166: "166px",
        194: "194px",
        269: "269px",
      },
      height: {
        96: "96px",
      },
      fontFamily: {
        cisco: ["CiscoSans", "Inter"],
        inter: ["Inter"],
      },
      animation: {
        fadeInDropdown: "fadeInDropdown 0.3s ease-out",
        scaleIn: "scaleIn 0.25s ease-in-out",
      },
      keyframes: {
        fadeInDropdown: {
          from: {
            opacity: "0",
            transform: "translateY(10px)",
          },
          to: {
            opacity: "1",
            transform: "translateY(0)",
          },
        },
        scaleIn: {
          from: {
            transform: "scale(0.3)",
          },
          to: {
            transform: "scale(1)",
          },
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [tailwindcssAnimate],
}
