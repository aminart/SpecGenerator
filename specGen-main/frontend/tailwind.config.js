import typography from "@tailwindcss/typography";
import nightNavy from "night-navy/tailwind-v3-preset";

/**
 * Couleurs, police et arrondis : design system commun Night Navy (github:aminart/Design-system-).
 * Les noms historiques (navy, ink, line, ground, success) restent valables et suivent le thème clair / sombre.
 * Pour du texte, utiliser text-accent (text-navy suit le fond du bouton principal, trop foncé en sombre).
 */
/** @type {import('tailwindcss').Config} */
export default {
  presets: [nightNavy],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  plugins: [typography],
};
