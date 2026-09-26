import { useEffect } from "react";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/** A yes/no question before something destructive. Escape or a click outside cancels. */
export default function ConfirmDialog({ title, message, confirmLabel, onConfirm, onCancel }: ConfirmDialogProps) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div className="modal-overlay open" onClick={(event) => event.target === event.currentTarget && onCancel()}>
      <div className="modal-card" style={{ maxWidth: 420 }} role="alertdialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onCancel}>✕</button>
        </div>
        <div className="modal-body">
          <p>{message}</p>
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
            <button type="button" className="btn btn-outline" autoFocus onClick={onCancel}>Cancel</button>
            <button type="button" className="btn btn-outline btn-danger" onClick={onConfirm}>{confirmLabel}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
