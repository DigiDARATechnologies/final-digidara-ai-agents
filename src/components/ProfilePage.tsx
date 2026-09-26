import type { User } from "../types";

interface ProfilePageProps {
  open: boolean;
  user: User;
  onClose: () => void;
}

export default function ProfilePage({ open, user, onClose }: ProfilePageProps) {
  return (
    <div
      className={`modal-overlay${open ? " open" : ""}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-card modal-card-wide">
        <div className="modal-head">
          <h3>Profile</h3>
          <button className="icon-btn" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="modal-body">
          <div className="profile-avatar-row">
            <span className="avatar profile-avatar">{user.initial}</span>
            <div>
              <b>{user.name}</b>
              <br />
              <span className="muted">{user.email}</span>
            </div>
          </div>
          <div className="setting-row">
            <div>
              <b>Mobile</b>
              <br />
              <span className="muted">{user.mobile || "Not set"}</span>
            </div>
          </div>
          <div className="setting-row">
            <div>
              <b>Account ID</b>
              <br />
              <span className="muted mono">{user.id}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
