/**
 * Shared access to the vocabulary registry.
 *
 * One in-memory cache per page load, shared by every caller, so a page with a
 * dialect picker in three places issues one request instead of three. The cache
 * is invalidated explicitly (refresh()) rather than by a timer: the registry
 * only changes when an admin approves or edits something, and those actions
 * happen in this app, so we know exactly when to refetch.
 */

import { useCallback, useEffect, useState } from "react";
import {
  getVocabularyRegistry,
  type RegistryDialect,
  type RegistryProfile,
  type VocabularyRegistry,
} from "../api/vocabulary";

type Listener = (s: RegistryState) => void;

export interface RegistryState {
  loading: boolean;
  error: string | null;
  registryVersion: number;
  dialects: RegistryDialect[];
  profiles: RegistryProfile[];
}

const EMPTY: RegistryState = {
  loading: true,
  error: null,
  registryVersion: 0,
  dialects: [],
  profiles: [],
};

let cache: RegistryState = EMPTY;
let inFlight: Promise<void> | null = null;
const listeners = new Set<Listener>();

function publish(next: RegistryState) {
  cache = next;
  listeners.forEach((fn) => fn(next));
}

function load(force = false): Promise<void> {
  if (inFlight) return inFlight;
  if (!force && !cache.loading && cache.dialects.length > 0) return Promise.resolve();

  inFlight = getVocabularyRegistry()
    .then((res) => {
      if (res.ok) {
        const data: VocabularyRegistry = res.data;
        publish({
          loading: false,
          error: null,
          registryVersion: data.registry_version,
          dialects: data.dialects,
          profiles: data.profiles,
        });
      } else {
        // Deliberately NOT falling back to a hardcoded list. A silent fallback
        // is how the old two-map setup drifted from the database in the first
        // place; surfacing the error keeps the failure visible.
        publish({ ...cache, loading: false, error: res.error });
      }
    })
    .finally(() => {
      inFlight = null;
    });

  return inFlight;
}

export function useVocabularyRegistry(): RegistryState & { refresh: () => Promise<void> } {
  const [state, setState] = useState<RegistryState>(cache);

  useEffect(() => {
    listeners.add(setState);
    void load();
    return () => {
      listeners.delete(setState);
    };
  }, []);

  const refresh = useCallback(() => load(true), []);

  return { ...state, refresh };
}

/** Reset between tests; not used by app code. */
export function __resetVocabularyRegistryCache() {
  cache = EMPTY;
  inFlight = null;
  listeners.clear();
}
