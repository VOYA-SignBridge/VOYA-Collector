import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { me as fetchMe } from "../api/auth";
import type { AuthUser } from "../api/auth";
import { loadAuthToken } from "../api/axiosClient";

const AUTH_EVENT = "voya:auth-change";

export interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  isAuthenticated: false,
  isAdmin: false,
});

/**
 * Cheap "might I have a session?" check so guests never pay a pointless
 * /auth/me round-trip. Works across the auth transport transition:
 *  - legacy: a Bearer token in localStorage
 *  - cookie world: a readable, non-sensitive `voya_auth` hint cookie set by the
 *    backend alongside the httpOnly auth cookie (JS cannot read httpOnly).
 */
export function hasSessionHint(): boolean {
  if (loadAuthToken()) return true;
  return document.cookie
    .split("; ")
    .some((c) => c.startsWith("voya_auth="));
}

/**
 * Single source of truth for the current user. Fetches /auth/me ONCE for the
 * whole app (previously Layout, every useAuth() consumer, and each
 * ProtectedRoute fetched it independently — up to 3x per page load) and
 * re-fetches only on login/logout (AUTH_EVENT) or a cross-tab storage change.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      // Guests have no session — skip the /auth/me round-trip entirely.
      if (!hasSessionHint()) {
        if (mounted) {
          setUser(null);
          setLoading(false);
        }
        return;
      }
      if (mounted) setLoading(true);
      try {
        const u = await fetchMe();
        if (mounted) setUser(u);
      } catch {
        if (mounted) setUser(null);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    load();

    const handleAuthChange = () => load();
    window.addEventListener(AUTH_EVENT, handleAuthChange);
    window.addEventListener("storage", handleAuthChange);
    return () => {
      mounted = false;
      window.removeEventListener(AUTH_EVENT, handleAuthChange);
      window.removeEventListener("storage", handleAuthChange);
    };
  }, []);

  const value: AuthState = {
    user,
    loading,
    isAuthenticated: !!user,
    isAdmin: user?.is_admin ?? false,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Read the shared auth state. Same return shape as the old standalone hook, so
 * existing consumers (Dashboard/Upload/Labels/ResultsInsights) need no changes.
 */
export function useAuth(): AuthState {
  return useContext(AuthContext);
}
