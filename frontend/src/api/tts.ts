import axiosClient from "./axiosClient";

/**
 * TTS voice metadata from server.
 */
export interface TTSVoice {
  id: string;
  name: string;
  gender: "male" | "female";
  description: string;
}

export interface TTSVoicesResponse {
  voices: TTSVoice[];
  default: string;
}

/**
 * GET /api/v1/tts/voices
 *
 * Fetch available Vietnamese TTS voices from backend.
 */
export async function fetchTTSVoices(): Promise<TTSVoicesResponse | null> {
  try {
    const res = await axiosClient.get("/api/v1/tts/voices");
    return res.data as TTSVoicesResponse;
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    console.warn("[tts] voices fetch failed:", msg);
    return null;
  }
}

/**
 * GET /api/v1/tts/speak?text=...&voice=...
 *
 * Fetch synthesized audio (MP3) from backend TTS service.
 * Returns a Blob that can be used with URL.createObjectURL() and Audio().
 *
 * Returns null on failure (network error, 4xx/5xx).
 */
export async function fetchTTSAudio(
  text: string,
  voice?: string,
): Promise<Blob | null> {
  try {
    const params = new URLSearchParams({ text });
    if (voice) {
      params.set("voice", voice);
    }

    const res = await axiosClient.get(`/api/v1/tts/speak?${params.toString()}`, {
      responseType: "blob",
      // Short timeout for TTS: cached responses are instant;
      // uncached need edge-tts synthesis (~200-500ms).
      timeout: 5000,
    });

    if (res.status === 200 && res.data instanceof Blob && res.data.size > 0) {
      return res.data;
    }

    console.warn("[tts] unexpected response status:", res.status);
    return null;
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    if (import.meta.env.DEV) {
      console.warn("[tts] audio fetch failed:", msg);
    }
    return null;
  }
}
