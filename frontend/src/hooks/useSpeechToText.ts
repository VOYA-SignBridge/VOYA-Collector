import { useCallback, useEffect, useRef, useState } from "react";

// Simple abstraction over Web Speech API now, with a future path
// to swap to backend-based speech recognition via VITE_STT_MODE.

type BrowserSpeechRecognitionEvent = Event & {
  results: SpeechRecognitionResultList;
};

type BrowserSpeechRecognitionErrorEvent = Event & {
  error: string;
};

type BrowserSpeechRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onstart: ((this: BrowserSpeechRecognition, ev: Event) => void) | null;
  onerror:
    | ((this: BrowserSpeechRecognition, ev: BrowserSpeechRecognitionErrorEvent) => void)
    | null;
  onend: ((this: BrowserSpeechRecognition, ev: Event) => void) | null;
  onresult:
    | ((this: BrowserSpeechRecognition, ev: BrowserSpeechRecognitionEvent) => void)
    | null;
};

type BrowserSpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

export type SpeechToTextMode = "browser" | "backend";

export interface UseSpeechToTextOptions {
  // Called when a full recognition result is available
  onResult?: (text: string) => void;
}

export interface UseSpeechToTextValue {
  listening: boolean;
  supported: boolean;
  error: string | null;
  start: (options?: UseSpeechToTextOptions) => void;
  stop: () => void;
}

export function useSpeechToText(): UseSpeechToTextValue {
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const callbackRef = useRef<UseSpeechToTextOptions["onResult"] | null>(null);

  const mode: SpeechToTextMode = (import.meta.env.VITE_STT_MODE as SpeechToTextMode) || "browser";
  const lang = import.meta.env.VITE_STT_LANG || "vi-VN";

  // Initialize Web Speech API recognition instance when in browser mode
  useEffect(() => {
    if (typeof window === "undefined") return;

    if (mode !== "browser") {
      // Backend mode will be implemented later; for now just mark as unsupported
      setSupported(false);
      return;
    }

    interface WindowWithSpeechRecognition extends Window {
      SpeechRecognition?: BrowserSpeechRecognitionConstructor;
      webkitSpeechRecognition?: BrowserSpeechRecognitionConstructor;
    }

    const win = window as WindowWithSpeechRecognition;
    const SR = win.SpeechRecognition || win.webkitSpeechRecognition;
    if (!SR) {
      setSupported(false);
      setError("Trình duyệt không hỗ trợ Web Speech API");
      return;
    }

    const recognition: BrowserSpeechRecognition = new SR();
    recognition.lang = lang;
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
      setListening(true);
      setError(null);
    };

    recognition.onerror = (event: BrowserSpeechRecognitionErrorEvent) => {
      setError(event.error || "Lỗi nhận dạng giọng nói");
      setListening(false);
    };

    recognition.onend = () => {
      setListening(false);
    };

    recognition.onresult = (event: BrowserSpeechRecognitionEvent) => {
      try {
        const result = event.results?.[0]?.[0];
        if (result && typeof result.transcript === "string") {
          const text = result.transcript.trim();
          if (text && callbackRef.current) {
            callbackRef.current(text);
          }
        }
      } catch (e) {
        console.warn("Speech recognition result error", e);
      }
    };

    recognitionRef.current = recognition;
    setSupported(true);

    return () => {
      recognitionRef.current = null;
    };
    // mode/lang are static from env; we intentionally don't re-create instance on change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const start = useCallback((options?: UseSpeechToTextOptions) => {
    callbackRef.current = options?.onResult;

    if (mode !== "browser") {
      console.warn("Speech-to-text backend mode chưa được triển khai");
      setError("Chế độ backend STT chưa được cấu hình");
      return;
    }

    const recognition = recognitionRef.current;
    if (!recognition) {
      setError("Trình duyệt không hỗ trợ nhận dạng giọng nói");
      return;
    }

    try {
      recognition.start();
    } catch (e) {
      // start() có thể throw nếu đã đang chạy
      console.warn("Speech recognition start error", e);
      setError("Không thể bắt đầu nhận dạng, thử lại");
    }
  }, [mode]);

  const stop = useCallback(() => {
    const recognition = recognitionRef.current;
    if (!recognition) return;
    try {
      recognition.stop();
    } catch (e) {
      console.warn("Speech recognition stop error", e);
    }
  }, []);

  return { listening, supported, error, start, stop };
}

export default useSpeechToText;
