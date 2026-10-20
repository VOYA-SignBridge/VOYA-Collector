import apiClient from "./axiosClient";

export interface SignerRow {
  signer_id: string;
  display_name: string;
  regional_group: string;
  external_user_id: string;
  is_active: boolean;
  created_at: string;
  sample_count: number;
  class_count: number;
  last_sample_at: string | null;
  consent_state: "granted" | "withdrawn" | "none";
  consent_scope: string | null;
  merged_into: string | null;
  merged_reason: string | null;
}

export interface SignersResponse {
  signers: SignerRow[];
  tenant_id: string;
  total_samples: number;
  unattributed_samples: number;
  scope_ladder: string[];
}

export interface UpdateSignerBody {
  display_name?: string;
  regional_group?: string;
  is_active?: boolean;
}

export const getSigners = () =>
  apiClient.get<SignersResponse>("/api/v1/admin/signers").then((r) => r.data);

export const updateSigner = (signerId: string, body: UpdateSignerBody) =>
  apiClient
    .patch<SignerRow>(`/api/v1/admin/signers/${encodeURIComponent(signerId)}`, body)
    .then((r) => r.data);

export const mergeSigner = (signerId: string, targetSignerId: string, reason: string) =>
  apiClient
    .post(`/api/v1/admin/signers/${encodeURIComponent(signerId)}/merge`, {
      target_signer_id: targetSignerId,
      reason,
    })
    .then((r) => r.data);
