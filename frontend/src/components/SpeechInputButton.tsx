import Button from "./ui/Button";
import useSpeechToText from "../hooks/useSpeechToText";

interface SpeechInputButtonProps {
  onText: (text: string) => void;
  title?: string;
  className?: string;
}

// Small mic button that toggles speech recognition and
// passes recognized text back via onText.
export default function SpeechInputButton({ onText, title, className }: SpeechInputButtonProps) {
  const { listening, supported, error, start, stop } = useSpeechToText();

  const handleClick = () => {
    if (!supported) {
      window.alert(error || "Trình duyệt không hỗ trợ microphone / Web Speech API");
      return;
    }

    if (listening) {
      stop();
      return;
    }

    start({
      onResult: (text) => {
        onText(text);
      },
    });
  };

  const label = listening ? "Đang ghi âm, hãy đọc" : "Nhấn để đọc bằng giọng nói";

  return (
    <Button
      type="button"
      onClick={handleClick}
      variant="secondary"
      className={
        "h-9 w-9 p-0 flex flex-col items-center justify-center rounded-full border text-[10px] transition-colors duration-150 " +
        (listening
          ? "!bg-red-600 !border-red-400 text-white ring-2 ring-red-400 ring-offset-1 ring-offset-gray-900 animate-pulse"
          : "!bg-sky-600 !border-sky-500 text-white hover:!bg-sky-500") +
        (className ? " " + className : "")
      }
      title={title || label}
    >
      <svg
        className="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 1a3 3 0 00-3 3v7a3 3 0 006 0V4a3 3 0 00-3-3z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M19 10v1a7 7 0 11-14 0v-1m7 7v4m-4 0h8"
        />
      </svg>
      {listening && (
        <span className="mt-0.5 text-[9px] leading-none text-red-100">Đang nghe…</span>
      )}
      <span className="sr-only">{label}</span>
    </Button>
  );
}
