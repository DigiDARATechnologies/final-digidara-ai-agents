import type { ReactNode } from "react";

/** Line icons in the same style as the sidebar nav (24px grid, 1.7 stroke).
 * Agents and industries store one of these keys in their `icon` field. */
const PATHS: Record<string, ReactNode> = {
  compass: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M15.5 8.5l-2 5-5 2 2-5 5-2z" />
    </>
  ),
  code: <path d="M8.5 7L3.5 12l5 5M15.5 7l5 5-5 5M13.5 5l-3 14" />,
  terminal: (
    <>
      <rect x="3.5" y="4.5" width="17" height="15" rx="2.5" />
      <path d="M7.5 10l3 2.5-3 2.5M13 15h3.5" />
    </>
  ),
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6" />
      <path d="M15 15l5 5" />
    </>
  ),
  book: (
    <>
      <path d="M5 4.5h10.5a3 3 0 013 3V20H8a3 3 0 01-3-3V4.5z" />
      <path d="M5 17a3 3 0 013-3h10.5" />
    </>
  ),
  pen: (
    <>
      <path d="M4 20l1-4.5L16.5 4a2.1 2.1 0 013 3L8 18.5 4 20z" />
      <path d="M14.5 6l3 3" />
    </>
  ),
  chart: (
    <>
      <path d="M4 20V4" />
      <path d="M4 20h16" />
      <path d="M8.5 16v-4M13 16V8M17.5 16v-6" />
    </>
  ),
  calculator: (
    <>
      <rect x="5" y="3.5" width="14" height="17" rx="2.5" />
      <path d="M8.5 7.5h7M8.5 12h.01M12 12h.01M15.5 12h.01M8.5 16h.01M12 16h.01M15.5 16h.01" />
    </>
  ),
  mic: (
    <>
      <rect x="9" y="3.5" width="6" height="11" rx="3" />
      <path d="M5.5 11.5a6.5 6.5 0 0013 0M12 18v3" />
    </>
  ),
  video: (
    <>
      <rect x="3.5" y="6" width="12" height="12" rx="2.5" />
      <path d="M15.5 10.5l5-2.5v8l-5-2.5" />
    </>
  ),
  briefcase: (
    <>
      <rect x="3.5" y="7.5" width="17" height="12" rx="2.5" />
      <path d="M9 7.5v-2a1.5 1.5 0 011.5-1.5h3A1.5 1.5 0 0115 5.5v2M3.5 13h17" />
    </>
  ),
  cap: (
    <>
      <path d="M2.5 9.5L12 5l9.5 4.5L12 14 2.5 9.5z" />
      <path d="M6.5 11.8V16c0 1.2 2.5 2.5 5.5 2.5s5.5-1.3 5.5-2.5v-4.2M21.5 9.5V15" />
    </>
  ),
  chat: <path d="M4 5.5h16a1 1 0 011 1V16a1 1 0 01-1 1h-8l-4.5 3.5V17H4a1 1 0 01-1-1V6.5a1 1 0 011-1z" />,
  file: (
    <>
      <path d="M6 3.5h8l4.5 4.5v11.5a1 1 0 01-1 1H6a1 1 0 01-1-1v-15a1 1 0 011-1z" />
      <path d="M14 3.5V8h4.5M8.5 12.5h7M8.5 16h5" />
    </>
  ),
  award: (
    <>
      <circle cx="12" cy="9" r="5.5" />
      <path d="M8.8 13.6L7.5 21l4.5-2.5 4.5 2.5-1.3-7.4" />
    </>
  ),
  bolt: <path d="M13 3L5 13.5h6L10 21l8-10.5h-6L13 3z" />,
  plane: <path d="M21 4L3 11l6.5 2.5L12 20l2.5-6.5L21 4zM9.5 13.5L21 4" />,
  building: (
    <>
      <path d="M5 20.5V4.5a1 1 0 011-1h8a1 1 0 011 1v16M15 9.5h3a1 1 0 011 1v10M3.5 20.5h17" />
      <path d="M8.5 7.5h3M8.5 11h3M8.5 14.5h3" />
    </>
  ),
  heart: <path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0112 7.3a4.3 4.3 0 017.5 2.5C19.5 15.4 12 20 12 20z" />,
  bank: <path d="M3.5 9.5L12 4l8.5 5.5M5.5 9.5v8M10 9.5v8M14 9.5v8M18.5 9.5v8M3.5 20h17" />,
  rocket: (
    <>
      <path d="M12 3c3.5 2 5 5.5 4.5 10l-2 2.5h-5L7.5 13C7 8.5 8.5 5 12 3z" />
      <circle cx="12" cy="9.5" r="1.5" />
      <path d="M7.5 13L5 15.5V19l3.5-1.5M16.5 13l2.5 2.5V19l-3.5-1.5" />
    </>
  ),
  sparkle: <path d="M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9-1.9 5.1-1.9-5.1L5 10.5l5.1-1.9L12 3.5z" />,
};

interface AgentIconProps {
  /** A key from PATHS; anything else falls back to a sparkle. */
  name: string;
  size?: number | string;
}

export default function AgentIcon({ name, size = "1.15em" }: AgentIconProps) {
  return (
    <svg
      className="agent-icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name] ?? PATHS.sparkle}
    </svg>
  );
}
