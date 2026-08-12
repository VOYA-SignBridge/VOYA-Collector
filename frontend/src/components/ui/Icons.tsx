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

export function ClockIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 1.8" />
    </Icon>
  );
}

export function CloudDownloadIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M7 18.5a4 4 0 0 1-.5-7.97 5.5 5.5 0 0 1 10.6-1.02A3.75 3.75 0 0 1 17 18.5" />
      <path d="M12 12v6.5" />
      <path d="M9.3 15.8 12 18.5l2.7-2.7" />
    </Icon>
  );
}

export function CheckIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M5 12l5 5L20 7" />
    </Icon>
  );
}

export function XIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M18 6L6 18M6 6l12 12" />
    </Icon>
  );
}

export function AlertTriangleIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M12 4.2 21 19H3L12 4.2Z" />
      <path d="M12 10v4" />
      <circle cx="12" cy="16.8" r="0.15" fill="currentColor" stroke="none" />
    </Icon>
  );
}

export function InfoCircleIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 11v5.5" />
      <circle cx="12" cy="8" r="0.15" fill="currentColor" stroke="none" />
    </Icon>
  );
}

export function CopyIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="9" y="9" width="11" height="11" rx="1.5" />
      <path d="M6.5 15H5.5A1.5 1.5 0 0 1 4 13.5v-8A1.5 1.5 0 0 1 5.5 4h8A1.5 1.5 0 0 1 15 5.5v1" />
    </Icon>
  );
}

export function PlayCircleIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M10.3 8.7v6.6l5.4-3.3-5.4-3.3Z" />
    </Icon>
  );
}

export function ArrowUpCircleIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 15.5v-7M8.7 11.8 12 8.5l3.3 3.3" />
    </Icon>
  );
}

/* ------------------------------------------------------------------------
 * Bổ sung 2026-08-09 — thay emoji ở các mặt quản trị.
 *
 * Hình học lấy theo bộ Lucide (giấy phép ISC), bộ biểu tượng đứng sau
 * shadcn/ui. Không nhúng gói: chỉ vài biểu tượng thì một phụ thuộc mới tốn
 * nhiều byte hơn phần dùng tới, và mọi thứ ở đây phải là SVG nội tuyến —
 * biểu tượng tải từ CDN sẽ vỡ sau lưng tường lửa của trường.
 * ---------------------------------------------------------------------- */

export function ShieldIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M12 21.5c-4.2-1.4-7-4-7-8.5V6.2a1 1 0 0 1 .9-1c2-.2 4.2-1 6.1-2.2a1 1 0 0 1 1 0c1.9 1.2 4.1 2 6.1 2.2a1 1 0 0 1 .9 1V13c0 4.5-2.8 7.1-7 8.5Z" />
    </Icon>
  );
}

export function ShieldCheckIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M12 21.5c-4.2-1.4-7-4-7-8.5V6.2a1 1 0 0 1 .9-1c2-.2 4.2-1 6.1-2.2a1 1 0 0 1 1 0c1.9 1.2 4.1 2 6.1 2.2a1 1 0 0 1 .9 1V13c0 4.5-2.8 7.1-7 8.5Z" />
      <path d="m9.2 12.2 2 2 3.6-3.8" />
    </Icon>
  );
}

/** Sổ đăng bạ / nhật ký kiểm toán. */
export function ScrollTextIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M19 17V5a2 2 0 0 0-2-2H4" />
      <path d="M8 21h11a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3" />
      <path d="M14.5 8h-6M14.5 12h-6" />
    </Icon>
  );
}

/** Tổ chức / tenant. */
export function BuildingIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M6 21V4.5A1.5 1.5 0 0 1 7.5 3h6A1.5 1.5 0 0 1 15 4.5V21" />
      <path d="M15 9h2.5A1.5 1.5 0 0 1 19 10.5V21" />
      <path d="M4 21h17" />
      <path d="M9 7h3M9 11h3M9 15h3" />
    </Icon>
  );
}

export function XCircleIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m14.5 9.5-5 5M9.5 9.5l5 5" />
    </Icon>
  );
}

export function TrashIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 6.5h16" />
      <path d="M18 6.5V19a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6.5" />
      <path d="M9.5 6.5V5a1.5 1.5 0 0 1 1.5-1.5h2A1.5 1.5 0 0 1 14.5 5v1.5" />
      <path d="M10.5 11v5.5M13.5 11v5.5" />
    </Icon>
  );
}

export function DownloadIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M12 4v10.5" />
      <path d="m8 11 4 4 4-4" />
      <path d="M5 16.5V19a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 19v-2.5" />
    </Icon>
  );
}

export function MailIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3.5 6.5 8.5 6 8.5-6" />
    </Icon>
  );
}

export function SmartphoneIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="6.5" y="2.5" width="11" height="19" rx="2.5" />
      <path d="M10.5 18.5h3" />
    </Icon>
  );
}

/* ---------------------------------------------------------------------------
 * Đợt thứ hai — thay nốt ký hiệu tượng hình còn lại
 *
 * Ba mươi tệp vẫn dùng emoji làm biểu tượng. Lý do thay không phải thẩm mỹ:
 * emoji do **phông của hệ điều hành** vẽ, nên cùng một màn hình ra ba hình
 * khác nhau trên Windows, Android và máy Mac của hội đồng — và trên một máy
 * Windows thiếu phông màu thì nó ra ô vuông rỗng. Chúng cũng không nhận
 * `currentColor`, nên một biểu tượng cảnh báo vẫn vàng khi nằm trong khối màu
 * đỏ; và trình đọc màn hình đọc to tên Unicode của chúng giữa câu.
 *
 * Mọi biểu tượng dưới đây dùng chung `Icon`, nên chúng thừa kế màu và cỡ của
 * chỗ đặt vào — đúng ba thứ emoji không làm được.
 * ------------------------------------------------------------------------- */

export function ChevronDownIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="m6 9 6 6 6-6" />
    </Icon>
  );
}

export function ChevronRightIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="m9 6 6 6-6 6" />
    </Icon>
  );
}

export function ArrowRightIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 12h16" />
      <path d="m14 6 6 6-6 6" />
    </Icon>
  );
}

export function TrendUpIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="m3 17 6-6 4 4 8-8" />
      <path d="M15 7h6v6" />
    </Icon>
  );
}

export function TrendDownIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="m3 7 6 6 4-4 8 8" />
      <path d="M15 17h6v-6" />
    </Icon>
  );
}

export function ClipboardIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="7" y="4" width="10" height="17" rx="2" />
      <path d="M9.5 4V3h5v1" />
    </Icon>
  );
}

export function BanIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m5.6 5.6 12.8 12.8" />
    </Icon>
  );
}

export function FilmIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M8 4v16M16 4v16M3 12h18M3 8h5M3 16h5M16 8h5M16 16h5" />
    </Icon>
  );
}

export function EyeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="3" />
    </Icon>
  );
}

export function EyeOffIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 4l16 16" />
      <path d="M9.9 5.9A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-3.3 4.1" />
      <path d="M6.5 7.9A17 17 0 0 0 2.5 12S6 18.5 12 18.5a9.4 9.4 0 0 0 3.6-.7" />
      <path d="M9.9 10.2a3 3 0 0 0 4 4.1" />
    </Icon>
  );
}

export function TargetIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="1" />
    </Icon>
  );
}

export function PauseIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="7" y="5" width="3.5" height="14" rx="1" />
      <rect x="13.5" y="5" width="3.5" height="14" rx="1" />
    </Icon>
  );
}

export function StopIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </Icon>
  );
}

export function ChartBarIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 20h16" />
      <rect x="6" y="11" width="3.5" height="6" rx="1" />
      <rect x="11.5" y="7" width="3.5" height="10" rx="1" />
      <rect x="17" y="13" width="3" height="4" rx="1" />
    </Icon>
  );
}

export function PencilIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 20h4l10-10a2.1 2.1 0 0 0-3-3L5 17v3Z" />
      <path d="m14.5 6.5 3 3" />
    </Icon>
  );
}

export function UserIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20a7 7 0 0 1 14 0" />
    </Icon>
  );
}

export function CompassIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2 5-5 2 2-5Z" />
    </Icon>
  );
}

export function RepeatIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 9V8a3 3 0 0 1 3-3h10l-2.5-2.5" />
      <path d="M20 15v1a3 3 0 0 1-3 3H7l2.5 2.5" />
    </Icon>
  );
}

export function LightbulbIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M9 17a5.5 5.5 0 1 1 6 0v1.5a1.5 1.5 0 0 1-1.5 1.5h-3A1.5 1.5 0 0 1 9 18.5Z" />
      <path d="M10 21.5h4" />
    </Icon>
  );
}

export function LinkIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M10 13.5a3.5 3.5 0 0 0 5 0l3-3a3.5 3.5 0 0 0-5-5l-1.5 1.5" />
      <path d="M14 10.5a3.5 3.5 0 0 0-5 0l-3 3a3.5 3.5 0 0 0 5 5L12.5 17" />
    </Icon>
  );
}

export function BoltIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M13 2 4.5 13.5H11L10 22l8.5-11.5H12Z" />
    </Icon>
  );
}

export function HardDriveIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="3" y="12" width="18" height="7" rx="2" />
      <path d="m5.5 12 2-6.5h9l2 6.5" />
      <path d="M7 15.5h.01M10 15.5h.01" />
    </Icon>
  );
}

export function ServerIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="3" y="4" width="18" height="6" rx="2" />
      <rect x="3" y="14" width="18" height="6" rx="2" />
      <path d="M7 7h.01M7 17h.01" />
    </Icon>
  );
}

export function ThermometerIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M13.5 14V4.5a2 2 0 1 0-4 0V14a4 4 0 1 0 4 0Z" />
    </Icon>
  );
}

export function BellIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2.5h-15Z" />
      <path d="M10 19.5a2 2 0 0 0 4 0" />
    </Icon>
  );
}

export function BellOffIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 4l16 16" />
      <path d="M8 8.5V11a6 6 0 0 1-2 4.5v.5h11" />
      <path d="M18 16v-5a6 6 0 0 0-8.2-5.6" />
      <path d="M10 19.5a2 2 0 0 0 4 0" />
    </Icon>
  );
}

export function RulerIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="2.5" y="8.5" width="19" height="7" rx="1.5" />
      <path d="M7 8.5v3M11 8.5v4.5M15 8.5v3M19 8.5v4.5" />
    </Icon>
  );
}

export function TimerIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="13.5" r="7.5" />
      <path d="M12 9.5v4h3M9.5 2.5h5" />
    </Icon>
  );
}

export function RocketIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M13 3c4 1.5 6.5 5 7 9-4-.5-7.5-3-9-7l1-2Z" />
      <path d="M11 5C7 6.5 4.5 10 4 14c4-.5 7.5-3 9-7" />
      <path d="M9 15l-3 3" />
      <path d="M12.5 11.5a1.5 1.5 0 1 0 2.5 2.5" />
    </Icon>
  );
}

export function MapPinIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11Z" />
      <circle cx="12" cy="10" r="2.5" />
    </Icon>
  );
}

export function MapIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="m3 6 6-2 6 2 6-2v14l-6 2-6-2-6 2Z" />
      <path d="M9 4v14M15 6v14" />
    </Icon>
  );
}

export function AlphabetIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 17 8 7l4 10M5.4 14h5.2" />
      <path d="M15 10.5a2.5 2.5 0 1 1 4 2c-1 1-2.5 1.5-4 4.5h4.5" />
    </Icon>
  );
}

export function LockIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="5" y="10.5" width="14" height="10" rx="2" />
      <path d="M8.5 10.5V8a3.5 3.5 0 1 1 7 0v2.5" />
    </Icon>
  );
}

export function UnlockIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="5" y="10.5" width="14" height="10" rx="2" />
      <path d="M8.5 10.5V8a3.5 3.5 0 0 1 6.8-1.2" />
    </Icon>
  );
}

export function MoonIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" />
    </Icon>
  );
}

export function StarIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="m12 3.5 2.6 5.5 5.9.8-4.3 4.2 1.1 6-5.3-2.9-5.3 2.9 1.1-6L3.5 9.8l5.9-.8Z" />
    </Icon>
  );
}

export function MedalIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="15" r="5.5" />
      <path d="M8.5 10 6 3h12l-2.5 7" />
    </Icon>
  );
}

export function CrownIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M3 7.5 7 12l5-6.5 5 6.5 4-4.5-1.5 11h-15Z" />
    </Icon>
  );
}

export function CloudIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M7.5 18.5a4.5 4.5 0 0 1-.4-9A6 6 0 0 1 18.4 11a3.8 3.8 0 0 1-.4 7.5Z" />
    </Icon>
  );
}

export function InboxIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M3 13.5 5.5 5h13L21 13.5V19a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 19Z" />
      <path d="M3 13.5h5a4 4 0 0 0 8 0h5" />
    </Icon>
  );
}

export function BugIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="7.5" y="8" width="9" height="12" rx="4.5" />
      <path d="M9.5 8a2.5 2.5 0 0 1 5 0" />
      <path d="M7.5 12H4M20 12h-3.5M7.5 16.5 4.5 19M16.5 16.5 19.5 19M7.5 9.5 5 7M16.5 9.5 19 7" />
    </Icon>
  );
}

export function HandsPrayIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M12 3.5 8 10v7a3 3 0 0 0 3 3h1V3.5Z" />
      <path d="M12 3.5 16 10v7a3 3 0 0 1-3 3h-1" />
    </Icon>
  );
}

/**
 * Trợ lý tự động. Cố ý KHÔNG dùng biểu tượng người: câu trả lời của máy phải
 * nhìn ra là của máy ngay từ biểu tượng, trước cả khi đọc nhãn.
 */
export function RobotIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="4" y="8" width="16" height="11" rx="3" />
      <path d="M12 5.5V8M9 13h.01M15 13h.01M9.5 16.5h5" />
      <circle cx="12" cy="4" r="1.2" />
      <path d="M4 12.5H2.5M21.5 12.5H20" />
    </Icon>
  );
}

/** Gửi lời nhắn. */
export function SendIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4.5 12 20 4.5 15.5 20l-3.8-5.8Z" />
      <path d="M11.7 14.2 20 4.5" />
    </Icon>
  );
}

/** Ba chấm — người bên kia đang gõ, hoặc menu thêm. */
export function DotsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="6" cy="12" r="1.2" />
      <circle cx="12" cy="12" r="1.2" />
      <circle cx="18" cy="12" r="1.2" />
    </Icon>
  );
}
