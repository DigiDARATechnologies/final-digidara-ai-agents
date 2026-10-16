import { useEffect, useState } from "react";
import { checkCertificateLink, downloadCertificateLink, openSharedChat, type SharedChat, type SharedLink } from "../lib/linksApi";
import { renderMessageText } from "../lib/messageText";

interface Props {
  link: SharedLink;
  onClose: () => void;
  /** The owner opened their own chat's link: open it in their chat list. */
  onOpenOwnChat?: (chatId: string) => void;
}

/**
 * A link Boss made, opened: a chat shown read-only, or a certificate to
 * download. The server decides who may open it -- a private chat link and a
 * certificate link only for the account that made them, a public chat link
 * for any signed-in account -- and this shows its answer.
 */
export default function SharedLinkView({ link, onClose, onOpenOwnChat }: Props) {
  const [chat, setChat] = useState<SharedChat | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  useEffect(() => {
    let active = true;
    const load = link.kind === "chat"
      ? openSharedChat(link.token).then((shared) => { if (active) setChat(shared); })
      : checkCertificateLink(link.token);
    load.then(() => { if (active) setReady(true); })
      .catch((failure: Error) => { if (active) setError(failure.message); });
    return () => { active = false; };
  }, [link]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function download() {
    setDownloading(true);
    setError("");
    try {
      const { blob, filename } = await downloadCertificateLink(link.token);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
      setDownloaded(true);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setDownloading(false);
    }
  }

  const title = link.kind === "certificate" ? "Your certificate" : chat?.title || "Shared chat";
  return (
    <div className="modal-overlay open" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-card shared-link-card" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {error && <p className="shared-link-error" role="alert">{error}</p>}
          {!error && !ready && <p className="shared-link-note">Opening the link...</p>}
          {link.kind === "certificate" && ready && (
            <>
              <p className="shared-link-note">
                This download link is yours alone and works for 5 minutes from when Boss made it.
              </p>
              <button type="button" className="btn btn-primary" onClick={download} disabled={downloading}>
                {downloading ? "Downloading..." : downloaded ? "Download again" : "Download certificate (PDF)"}
              </button>
            </>
          )}
          {chat && (
            <>
              <p className="shared-link-note">
                {chat.is_owner
                  ? chat.mode === "public" ? "Your chat, shared with a public link (any signed-in DigiDARA account can open it)."
                    : "Your chat. This private link opens only for your account."
                  : `Shared by ${chat.owner_name || "a DigiDARA learner"}. Read only.`}
              </p>
              <div className="shared-chat">
                {chat.messages.map((message, index) => (
                  <div key={index} className={`shared-chat-msg ${message.role === "user" ? "user" : "agent"}`}>
                    <div className="bubble">{renderMessageText(message.text)}</div>
                    {message.time && <small>{message.time}</small>}
                  </div>
                ))}
                {chat.messages.length === 0 && <p className="shared-link-note">This chat has no messages yet.</p>}
              </div>
              {chat.is_owner && chat.chat_id && onOpenOwnChat && (
                <button type="button" className="btn btn-primary" onClick={() => onOpenOwnChat(chat.chat_id!)}>Open this chat</button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
