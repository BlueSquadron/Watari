import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Theme = "dark" | "light";

interface ThemeState {
  theme: Theme;
  toggle: () => void;
  set: (theme: Theme) => void;
}

function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
  root.dataset.theme = theme;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: "dark",
      toggle: () => {
        const next = get().theme === "dark" ? "light" : "dark";
        applyTheme(next);
        set({ theme: next });
      },
      set: (theme) => {
        applyTheme(theme);
        set({ theme });
      },
    }),
    {
      name: "watari-theme",
      onRehydrateStorage: () => (state) => {
        if (state) applyTheme(state.theme);
      },
    },
  ),
);
