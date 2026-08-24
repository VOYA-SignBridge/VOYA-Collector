import apiClient from "./axiosClient";

export interface CollectionSession {
  capture_session_id: string;
  session_id: string;
  class_uid: string;
  label: string | null;
  dialect: string | null;
  signer_id: string | null;
  signer_name: string | null;
  contributor: string | null;
  source_type: string | null;
  started_at: string | null;
  ended_at: string | null;
  note: string | null;
  sample_count: number;
  is_open: boolean;
  is_mine: boolean;
}

export interface SessionsResponse {
  sessions: CollectionSession[];
  tenant_id: string;
  total: number;
  open_count: number;
  /** Phạm vi máy chủ ĐÃ áp dụng — không phải phạm vi được yêu cầu. */
  scope: "mine" | "tenant";
}

export const getSessions = (scope: "auto" | "mine" | "tenant" = "auto") =>
  apiClient
    .get<SessionsResponse>("/api/v1/sessions", { params: { scope } })
    .then((r) => r.data);

export const updateSession = (
  captureSessionId: string,
  body: { close?: boolean; note?: string },
) =>
  apiClient
    .patch(`/api/v1/sessions/${encodeURIComponent(captureSessionId)}`, body)
    .then((r) => r.data);
