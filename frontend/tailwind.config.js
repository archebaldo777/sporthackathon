/** Фирменный стиль ФСП (брендбук «Руководство по использованию фирменного стиля»):
 *  цвета логотипа #402FFF (акцентный/главный), #EC1D35 (акцентный/лого), #EDEDED; градации серого #1B1C21 · #2D2E37 ·
 *  #3A3C46 · #9B9C9E · #D9D9D9 · #EDEDED; digital-акцент #0A006B; цветовой код дисциплин ФСП;
 *  основной шрифт JetBrains Mono, акцентный — TDAText, текст интерфейса — Inter (основной шрифт флагманских проектов ФСП). */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { 50: "#F1EFFF", 100: "#E4E0FF", 200: "#C9C2FF", 300: "#A497FF", 400: "#7A68FF", 500: "#402FFF", 600: "#3424E0", 700: "#291BB3", 800: "#1F1585", 900: "#0A006B" },
        accent: { 50: "#FFF0F2", 100: "#FFDDE2", 500: "#EC1D35", 600: "#C9142A", 700: "#A10F21" },
        // текст: #1B1C21 и #3A3C46 — из брендбука; #62636B — затемнённый #9B9C9E для контраста AA на светлом фоне
        ink: { DEFAULT: "#1B1C21", 2: "#3A3C46", 3: "#62636B", 4: "#9B9C9E" },
        line: "#DCDCE0",
        surface: { DEFAULT: "#F3F3F4", 2: "#EDEDED" },
        night: { DEFAULT: "#1B1C21", 2: "#2D2E37", 3: "#3A3C46" },
        digital: "#0A006B",
        // цветовой код дисциплин ФСП
        disc: { product: "#8F1BF4", algorithmic: "#402FFD", uav: "#1ED3CA", robotics: "#ECB617", security: "#09A953" },
        ok: { 50: "#ECFDF3", 500: "#12A150", 700: "#0B7A3B" },
        warn: { 50: "#FFF8E6", 500: "#D98E04", 700: "#9A6400" },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        pixel: ["TDAText", '"JetBrains Mono"', "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(27,28,33,.04), 0 1px 3px rgba(27,28,33,.06)",
        lift: "0 10px 30px -12px rgba(64,47,255,.35)",
      },
      // строже, чем «мягкий» SaaS: брендбук ФСП — технические плашки с небольшим скруглением
      borderRadius: { lg: "7px", xl: "10px", "2xl": "12px" },
      keyframes: { "fade-in": { from: { opacity: 0, transform: "translateY(4px)" }, to: { opacity: 1, transform: "none" } } },
      animation: { "fade-in": "fade-in .25s ease-out both" },
    },
  },
  plugins: [],
};
