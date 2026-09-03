/**
 * Inventory Context
 *
 * Provides app-wide inventory state (locations list + helpers) via the shared
 * useInventory hook. Mirrors AuthContext.
 */

import { createContext, useContext } from 'react';
import { useInventory } from '@pantry-app/shared';

const InventoryContext = createContext(null);

export function InventoryProvider({ children }) {
  const inventory = useInventory();

  return (
    <InventoryContext.Provider value={inventory}>
      {children}
    </InventoryContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useInventoryContext() {
  const context = useContext(InventoryContext);

  if (!context) {
    throw new Error('useInventoryContext must be used within InventoryProvider');
  }

  return context;
}
