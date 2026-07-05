import type { InputHTMLAttributes, ReactNode } from "react";

export function UserIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5">
      <circle cx="12" cy="8" r="3.25" />
      <path strokeLinecap="round" d="M5 19.5c1.2-3.4 4-5 7-5s5.8 1.6 7 5" />
    </svg>
  );
}

export function MailIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5">
      <rect x="3.5" y="5.5" width="17" height="13" rx="2" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 7l8 6 8-6" />
    </svg>
  );
}

export function LockIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5">
      <rect x="4.5" y="10.5" width="15" height="9.5" rx="2" />
      <path strokeLinecap="round" d="M7.5 10.5V8a4.5 4.5 0 0 1 9 0v2.5" />
    </svg>
  );
}

interface AuthInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  icon: ReactNode;
  error?: string;
  trailing?: ReactNode;
}

export default function AuthInput({ label, icon, error, trailing, className, ...rest }: AuthInputProps) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>
      <div className="relative">
        <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-ctu-blue/70">
          {icon}
        </span>
        <input
          {...rest}
          aria-invalid={!!error}
          className={`w-full rounded-xl border bg-white py-3 pl-11 text-slate-900 shadow-sm outline-none transition focus:border-ctu-blue focus:ring-4 focus:ring-ctu-blue/15 ${
            trailing ? "pr-16" : "pr-4"
          } ${error ? "border-red-300" : "border-slate-200"} ${className ?? ""}`}
        />
        {trailing ? <span className="absolute inset-y-0 right-2 flex items-center">{trailing}</span> : null}
      </div>
      {error ? <span className="mt-1.5 block text-sm text-red-600">{error}</span> : null}
    </label>
  );
}
