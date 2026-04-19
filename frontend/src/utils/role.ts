// Lightweight client-side role helper for demo/admin gating.
// Stores role in localStorage under 'voya_role' as either 'admin' or 'public'.
export type Role = 'admin' | 'public';

const KEY = 'voya_role';

export function getRole(): Role {
  try {
    const v = localStorage.getItem(KEY);
    if (v === 'admin') return 'admin';
  } catch {
    /* ignore */
  }
  return 'public';
}

export function isAdmin(): boolean {
  return getRole() === 'admin';
}

export function setRole(r: Role) {
  try {
    localStorage.setItem(KEY, r);
    // Notify other windows/components
    window.dispatchEvent(new Event('voya:rolechange'));
  } catch {
    // ignore
  }
}

export function toggleRole() {
  setRole(isAdmin() ? 'public' : 'admin');
}
