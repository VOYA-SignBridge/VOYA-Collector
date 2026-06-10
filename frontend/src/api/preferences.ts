import axiosClient from "./axiosClient";

/**
 * Fetch label autocomplete suggestions from the server.
 * Debounce this call on the client side (200ms recommended).
 */
export const fetchLabelSuggestions = async (
  q: string,
  language?: string,
  dialect?: string,
  limit: number = 10
): Promise<string[]> => {
  try {
    const params: Record<string, string | number> = { q, limit };
    if (language) params.language = language;
    if (dialect) params.dialect = dialect;
    const res = await axiosClient.get("/classes/suggest", { params });
    return res.data?.suggestions ?? [];
  } catch {
    return [];
  }
};

/**
 * Search collectors (signers) from sample data on the server.
 */
export const fetchCollectorSuggestions = async (
  q: string,
  language?: string,
  dialect?: string,
  limit: number = 10
): Promise<string[]> => {
  try {
    const params: Record<string, string | number> = { q, limit };
    if (language) params.language = language;
    if (dialect) params.dialect = dialect;
    const res = await axiosClient.get("/classes/collectors", { params });
    return res.data?.collectors ?? [];
  } catch {
    return [];
  }
};

/**
 * Get a user preference from server.
 */
export const getPreference = async (key: string): Promise<string | null> => {
  try {
    const res = await axiosClient.get("/classes/preferences", {
      params: { key },
    });
    return res.data?.value ?? null;
  } catch {
    return null;
  }
};

/**
 * Set a user preference on server.
 */
export const setPreference = async (
  key: string,
  value: string
): Promise<void> => {
  try {
    await axiosClient.post("/classes/preferences", { key, value });
  } catch {
    // Silent fail — non-critical
  }
};
