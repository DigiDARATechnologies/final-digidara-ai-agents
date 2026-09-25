import type { SaveStatus } from "../hooks/useAgentStatePersistence";

const MESSAGES: Partial<Record<SaveStatus, string>> = {
  loading: "Loading your saved progress...",
  saving: "Saving...",
  offline: "Offline: changes are not saved yet. Retrying...",
  rejected: "Some progress could not be saved because it is too large.",
};

export default function SaveIndicator({ status }: { status: SaveStatus }) {
  const message = MESSAGES[status];
  if (!message) return null;
  return (
    <div className={`save-indicator save-indicator--${status}`} role="status" aria-live="polite">
      {message}
    </div>
  );
}
