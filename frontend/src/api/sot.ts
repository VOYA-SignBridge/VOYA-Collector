import apiClient from "./axiosClient";

export interface SotMachine {
  name: string | null;
  fingerprint: string | null;
  public_key: string | null;
  added_at?: string | null;
  added_by?: string | null;
  note?: string | null;
  source: "committed" | "db";
  revocable: boolean;
}

export interface SotOverview {
  machines: SotMachine[];
  db_counts: Record<string, number>;
  schema_version: number;
  this_machine: { is_writer: boolean; fingerprint: string | null; public_key: string | null };
}

export interface SotRemoteFile {
  name: string;
  sha256: string;
  rows: number | null;
}

export interface SotRemote {
  available: boolean;
  published?: boolean;
  version?: string;
  machine?: string;
  signed_by?: string | null;
  trusted?: boolean;
  created_at?: string;
  schema_version?: number;
  row_counts?: Record<string, number>;
  files?: SotRemoteFile[];
  error?: string;
}

export interface SotSchema {
  schema_version: number;
  // schema_sql was removed on purpose: the endpoint no longer returns the raw
  // CREATE TABLE listing, so it cannot be rendered (or screenshotted) anywhere.
  required_columns: Record<string, string[]>;
}

export interface SotVerifyResult {
  ok: boolean;
  status?: string;
  version?: string | null;
  signed_by?: string | null;
  error?: string;
}

export interface RegisterMachineBody {
  name: string;
  note?: string;
  mode: "public_key" | "generate";
  public_key?: string;
}

export interface RegisterMachineResult {
  machine: SotMachine;
  private_key?: string;
  private_key_hint?: string;
}

export const getSotOverview = () =>
  apiClient.get<SotOverview>("/api/v1/admin/sot/overview").then((r) => r.data);

export const getSotRemote = () =>
  apiClient.get<SotRemote>("/api/v1/admin/sot/remote").then((r) => r.data);

export const getSotSchema = () =>
  apiClient.get<SotSchema>("/api/v1/admin/sot/schema").then((r) => r.data);

export const runSotVerify = () =>
  apiClient.post<SotVerifyResult>("/api/v1/admin/sot/verify").then((r) => r.data);

export const registerSotMachine = (body: RegisterMachineBody) =>
  apiClient.post<RegisterMachineResult>("/api/v1/admin/sot/machines", body).then((r) => r.data);

export const revokeSotMachine = (fingerprint: string) =>
  apiClient
    .delete(`/api/v1/admin/sot/machines/${encodeURIComponent(fingerprint)}`)
    .then((r) => r.data);
