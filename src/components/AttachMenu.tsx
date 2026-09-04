import { useEffect, useRef, useState } from "react";

interface AttachMenuProps {
  enabled: boolean;
  /** File input `accept` string for the "Upload document" option — varies
   * per agent (Capstone wants `.docx,.zip`; Resume Builder wants resume
   * documents). Photos always accept `image/*`. */
  documentAccept: string;
  onFiles: (files: FileList) => void;
  onDisabled: () => void;
  /** "icon" for the default composer's toolbar button, "text" for the
   * paste-composer's labeled button. */
  variant?: "icon" | "text";
  multiple?: boolean;
}

const PHOTO_ACCEPT = "image/*";

/** ChatGPT-style "+" attach control: clicking it opens a small dropdown
 * offering "Upload photo" vs "Upload document" instead of jumping straight
 * to the OS file picker. Both options funnel into the same `onFiles`
 * handler — callers don't need to know which one was used. */
export default function AttachMenu({
  enabled,
  documentAccept,
  onFiles,
  onDisabled,
  variant = "icon",
  multiple = false,
}: AttachMenuProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const photoInputRef = useRef<HTMLInputElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, [open]);

  function handleToggle(e: React.MouseEvent) {
    e.stopPropagation();
    if (!enabled) {
      onDisabled();
      return;
    }
    setOpen((v) => !v);
  }

  function pick(files: FileList | null) {
    if (files && files.length) onFiles(files);
  }

  return (
    <div className="attach-menu-wrap" ref={wrapRef}>
      <input
        ref={photoInputRef}
        type="file"
        accept={PHOTO_ACCEPT}
        multiple={multiple}
        style={{ display: "none" }}
        onChange={(e) => {
          pick(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={docInputRef}
        type="file"
        accept={documentAccept}
        multiple={multiple}
        style={{ display: "none" }}
        onChange={(e) => {
          pick(e.target.files);
          e.target.value = "";
        }}
      />

      {variant === "text" ? (
        <button type="button" className="btn btn-outline" title="Attach file" onClick={handleToggle}>
          📎 Attach file
        </button>
      ) : (
        <button type="button" className="icon-btn" title="Attach file" onClick={handleToggle}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M21 12.5l-8.5 8.5a4.5 4.5 0 01-6.4-6.4L14.6 6a3 3 0 014.3 4.3L10.4 18.7a1.5 1.5 0 01-2.2-2.2l7.6-7.6"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      )}

      <div className={`attach-menu-panel dropdown-panel${open && enabled ? " open" : ""}`}>
        <button
          type="button"
          className="attach-menu-item"
          onClick={() => {
            setOpen(false);
            photoInputRef.current?.click();
          }}
        >
          <span className="attach-menu-ico">🖼️</span>
          <span>Upload photo</span>
        </button>
        <button
          type="button"
          className="attach-menu-item"
          onClick={() => {
            setOpen(false);
            docInputRef.current?.click();
          }}
        >
          <span className="attach-menu-ico">📄</span>
          <span>Upload document</span>
        </button>
      </div>
    </div>
  );
}
