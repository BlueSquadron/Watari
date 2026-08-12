import { useNavigate } from "react-router-dom";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { clsx } from "clsx";
import { authApi } from "@/api/resources";
import { Button } from "@/components/common/Button";
import { useAuthStore } from "@/stores/auth";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useThemeStore } from "@/stores/theme";

export function TopBar() {
  const openPalette = useCommandPaletteStore((s) => s.open);
  const user = useAuthStore((s) => s.user);
  const logoutStore = useAuthStore((s) => s.logout);
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggle);
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      /* ignore */
    }
    logoutStore();
    navigate("/login");
  };

  return (
    <header className="flex h-14 items-center justify-between border-b border-watari-bg-dark-tertiary bg-watari-bg-dark px-4">
      <Button
        variant="secondary"
        size="sm"
        onClick={openPalette}
        className="w-80 justify-between"
      >
        <span className="flex items-center gap-2 text-watari-text-dark-secondary">
          <span>⌕</span>
          <span>Search or jump to…</span>
        </span>
        <kbd className="rounded bg-watari-bg-dark px-1.5 py-0.5 font-mono text-[10px] text-watari-text-dark-secondary">
          ⌘K
        </kbd>
      </Button>

      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          {theme === "dark" ? "☾" : "☀"}
        </Button>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              className={clsx(
                "flex items-center gap-2 rounded-md px-2 py-1 text-sm",
                "hover:bg-watari-bg-dark-tertiary",
              )}
            >
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-watari-gold text-xs font-semibold text-watari-bg-dark">
                {user?.display_name?.slice(0, 1) ?? "?"}
              </span>
              <span className="hidden sm:inline">{user?.display_name}</span>
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              className="min-w-[180px] rounded-md border border-watari-bg-dark-tertiary bg-watari-bg-dark-secondary p-1 shadow-lg"
              sideOffset={6}
              align="end"
            >
              <DropdownMenu.Label className="px-3 py-2 text-xs text-watari-text-dark-secondary">
                {user?.email}
              </DropdownMenu.Label>
              <DropdownMenu.Separator className="my-1 h-px bg-watari-bg-dark-tertiary" />
              <DropdownMenu.Item
                className="cursor-pointer rounded px-3 py-2 text-sm outline-none hover:bg-watari-bg-dark-tertiary"
                onSelect={handleLogout}
              >
                Sign out
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </header>
  );
}
