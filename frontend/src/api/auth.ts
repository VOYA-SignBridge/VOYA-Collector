import axiosClient from "./axiosClient";

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

export type LoginResponse = {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
};

export async function register(payload: RegisterPayload): Promise<AuthUser> {
  const res = await axiosClient.post("/api/v1/auth/register", payload);
  return res.data as AuthUser;
}

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  const res = await axiosClient.post("/api/v1/auth/login", payload);
  return res.data as LoginResponse;
}

export async function me(): Promise<AuthUser> {
  const res = await axiosClient.get("/api/v1/auth/me");
  return res.data as AuthUser;
}