import React, { useState } from "react";
import { resolveApiAssetUrl } from "../../api";

/** Shared photo avatar with the existing initials-and-color fallback. */
export default function StudentAvatar({
  avatarUrl,
  initials,
  avatarColor,
  className = "",
}) {
  const [failedAvatarUrl, setFailedAvatarUrl] = useState(null);
  const showImage = Boolean(avatarUrl) && failedAvatarUrl !== avatarUrl;

  return (
    <span
      className={`student-avatar ${className}`.trim()}
      style={showImage ? undefined : { backgroundColor: avatarColor }}
      aria-hidden="true"
    >
      {showImage ? (
        <img
          src={resolveApiAssetUrl(avatarUrl)}
          alt=""
          onError={() => setFailedAvatarUrl(avatarUrl)}
        />
      ) : (
        initials
      )}
    </span>
  );
}
