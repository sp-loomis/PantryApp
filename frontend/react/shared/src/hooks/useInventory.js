/**
 * useInventory Hook
 *
 * App-wide inventory state. For now this owns the locations list, which many
 * screens need (the locations index, the location <select> on the item form,
 * location-name lookups). Items and search results are fetched per-screen with
 * local state, so this stays small; mutating pages call `reloadLocations()`.
 *
 * Platform-agnostic (usable from web and future mobile).
 */

import { useState, useEffect, useCallback } from 'react';
import { listLocations } from '../services/inventoryService.js';

export function useInventory() {
  const [locations, setLocations] = useState([]);
  const [locationsLoading, setLocationsLoading] = useState(true);
  const [locationsError, setLocationsError] = useState(null);

  const reloadLocations = useCallback(async () => {
    try {
      setLocationsLoading(true);
      setLocationsError(null);
      const list = await listLocations();
      setLocations(list);
      return list;
    } catch (err) {
      setLocationsError(err);
      throw err;
    } finally {
      setLocationsLoading(false);
    }
  }, []);

  useEffect(() => {
    reloadLocations().catch(() => {
      /* error captured in state */
    });
  }, [reloadLocations]);

  /** Look up a location name by id (falls back to the id). */
  const locationName = useCallback(
    (locationId) =>
      locations.find((loc) => loc.location_id === locationId)?.name || locationId,
    [locations]
  );

  return {
    locations,
    locationsLoading,
    locationsError,
    reloadLocations,
    locationName,
  };
}
