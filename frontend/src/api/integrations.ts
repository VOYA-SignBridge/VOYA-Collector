/**
 * Khoá API và webhook.
 *
 * Điểm quan trọng nhất của module này nằm ở kiểu dữ liệu: `ApiKeyCreated` có
 * trường `key`, còn `ApiKey` thì KHÔNG. Đó không phải sơ suất — khoá thật chỉ
 * tồn tại trong câu trả lời của lượt tạo, và không endpoint nào đọc lại được
 * (backend chỉ lưu băm). Hai kiểu tách rời khiến trình biên dịch chặn mọi chỗ
 * cố hiển thị `key` từ danh sách, thay vì để chỗ đó hiện `undefined`.
 *
 * Cùng cấu trúc cho webhook: `WebhookCreated.secret` có, `Webhook.secret`
 * không.
 */

import axiosClient from "./axiosClient";

const API_PREFIX = "/api/v1/integrations";

export interface ApiKey {
  key_id: string;
  tenant_id: string;
  name: string;
  prefix: string;
  scopes: "read" | "write";
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
}

/** Chỉ trả về MỘT lần, ở đúng lượt tạo. */
export interface ApiKeyCreated {
  key_id: string;
  prefix: string;
  scopes: string;
  name: string;
  key: string;
}

export interface Webhook {
  endpoint_id: string;
  url: string;
  event_types: string;
  is_active: boolean;
  description: string;
  created_at: string;
  last_success_at: string | null;
  last_failure_at: string | null;
  failure_streak: number;
  disabled_at: string | null;
  disabled_reason: string | null;
}

/** Chỉ trả về MỘT lần, ở đúng lượt tạo. */
export interface WebhookCreated {
  endpoint_id: string;
  url: string;
  event_types: string;
  secret: string;
}

export interface Delivery {
  delivery_id: string;
  event_type: string;
  status: "pending" | "delivered" | "failed" | "dropped";
  attempts: number;
  last_status_code: number | null;
  last_error: string | null;
  next_attempt_at: string | null;
  created_at: string;
  delivered_at: string | null;
}

export async function fetchApiKeys(): Promise<ApiKey[]> {
  const res = await axiosClient.get(`${API_PREFIX}/api-keys`);
  return res.data;
}

export async function createApiKey(input: {
  name: string;
  scopes: "read" | "write";
  expires_in_days?: number | null;
}): Promise<ApiKeyCreated> {
  const res = await axiosClient.post(`${API_PREFIX}/api-keys`, input);
  return res.data;
}

export async function revokeApiKey(keyId: string): Promise<void> {
  await axiosClient.delete(`${API_PREFIX}/api-keys/${keyId}`);
}

export async function fetchEventTypes(): Promise<string[]> {
  const res = await axiosClient.get(`${API_PREFIX}/webhooks/event-types`);
  return res.data.event_types;
}

export async function fetchWebhooks(): Promise<Webhook[]> {
  const res = await axiosClient.get(`${API_PREFIX}/webhooks`);
  return res.data;
}

export async function createWebhook(input: {
  url: string;
  event_types: string;
  description: string;
}): Promise<WebhookCreated> {
  const res = await axiosClient.post(`${API_PREFIX}/webhooks`, input);
  return res.data;
}

export async function deleteWebhook(endpointId: string): Promise<void> {
  await axiosClient.delete(`${API_PREFIX}/webhooks/${endpointId}`);
}

export async function sendTestEvent(endpointId: string): Promise<{ delivery_id: string }> {
  const res = await axiosClient.post(`${API_PREFIX}/webhooks/${endpointId}/test`);
  return res.data;
}

export async function fetchDeliveries(endpointId: string, limit = 25): Promise<Delivery[]> {
  const res = await axiosClient.get(`${API_PREFIX}/webhooks/${endpointId}/deliveries`, {
    params: { limit },
  });
  return res.data;
}
