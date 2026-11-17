import { useSyncExternalStore } from "react";

/** Model picked at launch time among the Studio Dock models ("<connection id>|<model>"), for this session.
 * null: the default model (chosen in the settings). Sent with every request (header X-StudioDock-Model). */
let current: string | null = null;
const listeners = new Set<() => void>();

export function pickedModel(): string | null {
  return current;
}

export function pickModel(value: string | null): void {
  current = value || null;
  listeners.forEach((listener) => listener());
}

export function usePickedModel(): [string | null, (value: string | null) => void] {
  const value = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => current,
  );
  return [value, pickModel];
}
