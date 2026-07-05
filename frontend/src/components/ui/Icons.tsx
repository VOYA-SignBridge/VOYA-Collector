/**
 * Shared line-icon set (stroke-based, matches the style already established
 * in components/auth/AuthInput.tsx) — replaces emoji used as interface icons
 * across the sidebar and dashboard so they render consistently across
 * platforms instead of relying on OS emoji fonts.
 */
import type { SVGProps } from "react";

function Icon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    />
  );
}

export function HomeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 11.5 12 4l8 7.5" />
      <path d="M6 10v9.5a1 1 0 0 0 1 1h3.5v-6h3v6H17a1 1 0 0 0 1-1V10" />
    </Icon>
  );
}

export function UploadIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M12 15.5V5" />
      <path d="M8 8.5 12 4l4 4.5" />
      <path d="M5 15.5v3a1.5 1.5 0 0 0 1.5 1.5h11a1.5 1.5 0 0 0 1.5-1.5v-3" />
    </Icon>
  );
}

export function TagIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M12.5 4.5H7A2.5 2.5 0 0 0 4.5 7v5.5a1 1 0 0 0 .3.7l8 8a1 1 0 0 0 1.4 0l6.6-6.6a1 1 0 0 0 0-1.4l-8-8a1 1 0 0 0-.3-.2Z" />
      <circle cx="9" cy="9" r="1.4" fill="currentColor" stroke="none" />
    </Icon>
  );
}

export function HandIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M9 12.5V6a1.3 1.3 0 1 1 2.6 0v5" />
      <path d="M11.6 11V4.8a1.3 1.3 0 1 1 2.6 0V11" />
      <path d="M14.2 11.2V6.2a1.3 1.3 0 1 1 2.6 0v8.3" />
      <path d="M7 12.8V10a1.3 1.3 0 1 0-2.6 0v6.3C4.4 19.8 7.3 22 10.7 22h.9c3.4 0 6.2-2.8 6.2-6.2v-2.6" />
    </Icon>
  );
}

export function ChipIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="6" y="6" width="12" height="12" rx="2" />
      <rect x="9.5" y="9.5" width="5" height="5" rx="1" />
      <path d="M9 3v2.2M12 3v2.2M15 3v2.2M9 18.8V21M12 18.8V21M15 18.8V21M3 9h2.2M3 12h2.2M3 15h2.2M18.8 9H21M18.8 12H21M18.8 15H21" />
    </Icon>
  );
}

export function FolderIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 6.5A1.5 1.5 0 0 1 5.5 5H10l2 2.5h6a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5h-14A1.5 1.5 0 0 1 2.5 17V6.5Z" />
    </Icon>
  );
}

export function UsersIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="9" cy="8.5" r="3" />
      <path d="M3.5 19c.8-3 2.9-4.7 5.5-4.7s4.7 1.7 5.5 4.7" />
      <path d="M15.2 5.3a3 3 0 0 1 0 5.9" />
      <path d="M15.8 14.4c2.1.5 3.6 2.1 4.2 4.6" />
    </Icon>
  );
}

export function GlobeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c2.3 2.3 3.5 5.2 3.5 8.5s-1.2 6.2-3.5 8.5c-2.3-2.3-3.5-5.2-3.5-8.5S9.7 5.8 12 3.5Z" />
    </Icon>
  );
}

export function CameraIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2l1-1.8h6.9L16.5 7h2A1.5 1.5 0 0 1 20 8.5v9A1.5 1.5 0 0 1 18.5 19h-13A1.5 1.5 0 0 1 4 17.5Z" />
      <circle cx="12" cy="12.5" r="3.2" />
    </Icon>
  );
}

export function HeartIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M12 20s-7.2-4.4-9.5-9A5 5 0 0 1 12 6a5 5 0 0 1 9.5 5c-2.3 4.6-9.5 9-9.5 9Z" />
    </Icon>
  );
}

export function RefreshIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 12a8 8 0 0 1 13.7-5.7L20 8.5" />
      <path d="M20 4v4.5h-4.5" />
      <path d="M20 12a8 8 0 0 1-13.7 5.7L4 15.5" />
      <path d="M4 20v-4.5h4.5" />
    </Icon>
  );
}

export function DatabaseIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <ellipse cx="12" cy="6" rx="7.5" ry="3" />
      <path d="M4.5 6v6c0 1.66 3.36 3 7.5 3s7.5-1.34 7.5-3V6" />
      <path d="M4.5 12v6c0 1.66 3.36 3 7.5 3s7.5-1.34 7.5-3v-6" />
    </Icon>
  );
}

export function SplitIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 5h16" />
      <path d="M4 5v6a2 2 0 0 0 2 2h5" />
      <path d="M20 5v6a2 2 0 0 1-2 2h-5" />
      <path d="M12 13v6" />
      <circle cx="12" cy="20.2" r="1" fill="currentColor" stroke="none" />
    </Icon>
  );
}

export function SparkleIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M12 3.5c.5 3 2 4.5 5 5-3 .5-4.5 2-5 5-.5-3-2-4.5-5-5 3-.5 4.5-2 5-5Z" />
      <path d="M18.5 15c.25 1.4.95 2.1 2.35 2.35-1.4.25-2.1.95-2.35 2.35-.25-1.4-.95-2.1-2.35-2.35 1.4-.25 2.1-.95 2.35-2.35Z" />
    </Icon>
  );
}

export function GearIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 3.5v2.2M12 18.3v2.2M20.5 12h-2.2M5.7 12H3.5M17.7 6.3l-1.55 1.55M7.85 16.15 6.3 17.7M17.7 17.7l-1.55-1.55M7.85 7.85 6.3 6.3" />
    </Icon>
  );
}

export function ClipboardCheckIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="6" y="4.5" width="12" height="16" rx="1.5" />
      <path d="M9 4.5V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v.5" />
      <path d="M9 13.5l2 2 4-4.5" />
    </Icon>
  );
}

export function CheckCircleIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M8.3 12.3l2.6 2.6 5-5.4" />
    </Icon>
  );
}

export function SearchIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M19.2 19.2l-4-4" />
    </Icon>
  );
}

export function GraduationCapIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M2.5 9.5 12 5l9.5 4.5-9.5 4.5-9.5-4.5Z" />
      <path d="M6.5 11.6v4.1c0 1.4 2.46 2.8 5.5 2.8s5.5-1.4 5.5-2.8v-4.1" />
      <path d="M21 9.5v5" />
    </Icon>
  );
}
