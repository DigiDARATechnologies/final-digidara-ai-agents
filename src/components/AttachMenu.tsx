import { useEffect, useRef, useState } from "react";

interface AttachMenuProps {
  enabled: boolean;
  /** File input `accept` string for the "Upload document" option — varies
   * per agent (Capstone wants `.docx,.zip`; Resume Builder wants resume
   * documents). Photos always accept `image/*`. */
  documentAccept: string;
  onFiles: (files: FileList) => void;
  onDisabled: () => void;
  /** Called when this chat can't take the chosen kind (e.g. a zip in Resume Builder). */
  onUnsupported?: (message: string) => void;
  /** "icon" for the default composer's toolbar button, "text" for the
   * paste-composer's labeled button. */
  variant?: "icon" | "text";
  multiple?: boolean;
  /** Overrides the "+" button's class (the home screen styles its own). */
  buttonClassName?: string;
  /** Whether this chat can read a photo. Only chats that answer about an
   * image take one; elsewhere "Upload Photo" says what the chat does accept. */
  photoAllowed?: boolean;
}

const PHOTO_ACCEPT = "image/*";
const ZIP_ACCEPT = ".zip,application/zip,application/x-zip-compressed";

/** ChatGPT-style "+" attach control: clicking it opens a small dropdown
 * offering "Upload document", "Upload photo" and "Upload zip folder"
 * instead of jumping straight to the OS file picker. Both options funnel into the same `onFiles`
 * handler — callers don't need to know which one was used. */
export default function AttachMenu({
  enabled,
  documentAccept,
  onFiles,
  onDisabled,
  onUnsupported,
  variant = "icon",
  multiple = false,
  buttonClassName = "icon-btn attach-plus-btn",
  photoAllowed = true,
}: AttachMenuProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const photoInputRef = useRef<HTMLInputElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);
  const zipInputRef = useRef<HTMLInputElement>(null);

  // The agent's accept list may include ".zip"; that goes under its own
  // "Upload Zip Folder" option, and the document picker gets the rest.
  const acceptParts = documentAccept.split(",").map((part) => part.trim()).filter(Boolean);
  const zipAllowed = acceptParts.some((part) => part.toLowerCase() === ".zip");
  const docParts = acceptParts.filter((part) => part.toLowerCase() !== ".zip");
  const docAccept = docParts.join(",");
  const acceptedLabel = acceptParts.map((part) => part.replace(/^\./, "").toUpperCase()).join(", ");

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
    // The menu always opens so every option is visible; a chat that can't
    // take files says so when an option is chosen.
    setOpen((v) => !v);
  }

  function choose(input: HTMLInputElement | null, allowed: boolean, kind: string) {
    setOpen(false);
    if (!enabled) {
      onDisabled();
      return;
    }
    if (!allowed) {
      const accepted = acceptedLabel ? ` You can upload: ${acceptedLabel}.` : "";
      (onUnsupported ?? (() => onDisabled()))(`${kind} uploads aren't supported in this chat.${accepted}`);
      return;
    }
    input?.click();
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
        accept={docAccept}
        multiple={multiple}
        style={{ display: "none" }}
        onChange={(e) => {
          pick(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={zipInputRef}
        type="file"
        accept={ZIP_ACCEPT}
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
        <button type="button" className={buttonClassName} title="Attach file" aria-label="Attach file" aria-haspopup="menu" aria-expanded={open} onClick={handleToggle}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      )}

      <div className={`attach-menu-panel dropdown-panel${open ? " open" : ""}`}>
        <button type="button" className="attach-menu-item" onClick={() => choose(docInputRef.current, docParts.length > 0, "Document")}>
          <span className="attach-menu-ico">📄</span>
          <span>Upload Document</span>
        </button>
        <button type="button" className="attach-menu-item" onClick={() => choose(photoInputRef.current, photoAllowed, "Photo")}>
          <span className="attach-menu-ico">🖼️</span>
          <span>Upload Photo</span>
        </button>
        <button type="button" className="attach-menu-item" onClick={() => choose(zipInputRef.current, zipAllowed, "Zip folder")}>
          <span className="attach-menu-ico">🗜️</span>
          <span>Upload Zip Folder</span>
        </button>
      </div>
    </div>
  );
}
