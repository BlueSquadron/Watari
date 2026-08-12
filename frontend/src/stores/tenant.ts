import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UUID } from "@/types/api";

interface TenantState {
  activeTenantId: UUID | null;
  setActive: (tenantId: UUID) => void;
  clear: () => void;
}

export const useTenantStore = create<TenantState>()(
  persist(
    (set) => ({
      activeTenantId: null,
      setActive: (tenantId) => set({ activeTenantId: tenantId }),
      clear: () => set({ activeTenantId: null }),
    }),
    { name: "watari-tenant" },
  ),
);
