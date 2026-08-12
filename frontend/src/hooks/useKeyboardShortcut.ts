import { useEffect } from "react";

export interface ShortcutConfig {
  key: string;
  meta?: boolean;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  handler: (event: KeyboardEvent) => void;
  enabled?: boolean;
}

function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return true;
  return target.isContentEditable;
}

export function useKeyboardShortcut(shortcut: ShortcutConfig): void {
  useEffect(() => {
    if (shortcut.enabled === false) return;
    const listener = (event: KeyboardEvent) => {
      const keyMatches =
        event.key.toLowerCase() === shortcut.key.toLowerCase();
      const metaMatches = shortcut.meta ? event.metaKey : !event.metaKey;
      const ctrlMatches = shortcut.ctrl ? event.ctrlKey : !event.ctrlKey;
      const shiftMatches = shortcut.shift ? event.shiftKey : !event.shiftKey;
      const altMatches = shortcut.alt ? event.altKey : !event.altKey;
      if (
        keyMatches &&
        (shortcut.meta ? metaMatches : true) &&
        (shortcut.ctrl ? ctrlMatches : true) &&
        (shortcut.shift ? shiftMatches : true) &&
        (shortcut.alt ? altMatches : true)
      ) {
        // Allow Cmd/Ctrl+K even in inputs (that's the global command palette)
        if (isEditable(event.target) && !shortcut.meta && !shortcut.ctrl) {
          return;
        }
        event.preventDefault();
        shortcut.handler(event);
      }
    };
    document.addEventListener("keydown", listener);
    return () => document.removeEventListener("keydown", listener);
  }, [
    shortcut.key,
    shortcut.meta,
    shortcut.ctrl,
    shortcut.shift,
    shortcut.alt,
    shortcut.handler,
    shortcut.enabled,
  ]);
}
