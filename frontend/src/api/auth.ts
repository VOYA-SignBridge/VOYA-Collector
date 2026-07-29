import axiosClient, { clearAuthToken, setAuthToken } from "./axiosClient";

export type AuthUser = {
  id: string;
  username: string;
  email: string;
  is_active?: boolean;
  is_admin?: boolean;
  created_at?: string | null;
};

export type RegisterPayload = {
  username: string;
  email: string;
  password: string;
};

export type LoginPayload = {
  identifier: string;
  password: string;
};

export async function register(payload: RegisterPayload): Promise<AuthUser> {
  const res = await axiosClient.post("/api/v1/auth/register", payload);
  return res.data as AuthUser;
}

/** Login sets httpOnly auth cookies server-side and returns the user profile
 *  (no token in the body — the browser can't read the httpOnly cookies). */
export async function login(payload: LoginPayload): Promise<AuthUser> {
  const res = await axiosClient.post("/api/v1/auth/login", payload);
  // Purge any legacy localStorage Bearer token from the pre-cookie era: if it
  // lingered, every request would carry a stale Authorization header alongside
  // the fresh cookie and could shadow the new session.
  clearAuthToken();
  setAuthToken(null);
  return res.data as AuthUser;
}

/** Revoke the refresh token server-side and clear all auth cookies. */
export async function logout(): Promise<void> {
  try {
    await axiosClient.post("/api/v1/auth/logout");
  } catch {
    // Best-effort: even if the call fails, the client clears local state.
  }
}

export async function me(): Promise<AuthUser> {
  const res = await axiosClient.get("/api/v1/auth/me");
  return res.data as AuthUser;
}

export type MessageResponse = {
  message: string;
};

export async function forgotPassword(identifier: string): Promise<MessageResponse> {
  const res = await axiosClient.post("/api/v1/auth/forgot-password", { identifier });
  return res.data as MessageResponse;
}

export async function resetPassword(token: string, newPassword: string): Promise<MessageResponse> {
  const res = await axiosClient.post("/api/v1/auth/reset-password", {
    token,
    new_password: newPassword,
  });
  return res.data as MessageResponse;
}