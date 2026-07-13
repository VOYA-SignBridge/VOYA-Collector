/**
 * Backwards-compatible re-export. `useAuth` now reads from the shared
 * AuthProvider (see contexts/AuthContext.tsx) instead of each caller fetching
 * /auth/me itself. Return shape is unchanged: { user, loading, isAuthenticated,
 * isAdmin }, so existing consumers need no changes.
 */
export { useAuth } from "../contexts/AuthContext";
export type { AuthState } from "../contexts/AuthContext";
