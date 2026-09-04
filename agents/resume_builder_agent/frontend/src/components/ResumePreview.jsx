import { useEffect, useState } from "react";
import { previewResumePdf } from "../api/resumes.js";

export default function ResumePreview({ resume }) {
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewState, setPreviewState] = useState({
    type: "loading",
    message: "Preparing exact PDF preview…",
  });

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setPreviewState({ type: "loading", message: "Updating exact PDF preview…" });
      try {
        const blob = await previewResumePdf(resume);
        if (cancelled) return;
        const nextUrl = URL.createObjectURL(blob);
        setPreviewUrl((currentUrl) => {
          if (currentUrl) URL.revokeObjectURL(currentUrl);
          return nextUrl;
        });
        setPreviewState({ type: "ready", message: "Matches the downloaded PDF" });
      } catch (error) {
        if (!cancelled) setPreviewState({ type: "error", message: error.message });
      }
    }, 900);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [resume]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  return (
    <aside className="preview-panel">
      <div className="preview-panel-header">
        <div>
          <p className="eyebrow">Exact PDF Preview</p>
          <span className={`preview-sync-state ${previewState.type}`}>{previewState.message}</span>
        </div>
        <ul className="preview-checklist" aria-label="Preview verification">
          <li>Same data</li>
          <li>A4 PDF</li>
          <li>Selectable text</li>
        </ul>
      </div>
      <div className="preview-panel-scroll">
        {previewUrl ? (
          <iframe
            className="resume-pdf-preview"
            src={`${previewUrl}#toolbar=0&navpanes=0&view=FitH`}
            title="Resume PDF preview"
          />
        ) : (
          <div className="preview-loading-state" role="status">
            <span className="preview-spinner" aria-hidden="true" />
            <p>{previewState.message}</p>
          </div>
        )}
      </div>
    </aside>
  );
}
