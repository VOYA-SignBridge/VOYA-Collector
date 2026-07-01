import { useEffect, useState } from "react";
import { me as getMe } from "../api/auth";
import type { AuthUser } from "../api/auth";

const AUTH_EVENT = "voya:auth-change";

/**
 * Hook to get current authenticated user.
 * Listens to auth change events and refetches user data.
 * Returns null if not authenticated.
 */
export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadUser = async () => {
      setLoading(true);
      try {
        const userData = await getMe();
        setUser(userData);
      } catch (_err) {
        // 401 or fetch error → not authenticated
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    // Load on mount
    loadUser();

    // Listen for auth changes (login/logout)
    const handleAuthChange = () => {
      loadUser();
    };

    window.addEventListener(AUTH_EVENT, handleAuthChange);
    return () => window.removeEventListener(AUTH_EVENT, handleAuthChange);
  }, []);

  return {
    user,
    loading,
    isAuthenticated: !!user,
    isAdmin: user?.is_admin ?? false,
  };
}
