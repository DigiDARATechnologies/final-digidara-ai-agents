export interface ProfilePrefs {
  displayName?: string;
  username?: string;
  avatar?: string;
  mobile?: string;
}

// Optional +, then 7-15 digits; spaces, dashes and brackets are allowed as separators.
export function normalizeMobile(value: string): string | null {
  const cleaned = value.trim().replace(/[\s\-().]/g, "");
  return /^\+?\d{7,15}$/.test(cleaned) ? cleaned : null;
}

export const USERNAME_RE = /^[a-zA-Z0-9._-]{3,30}$/;

const key = (userId: string) => `digidara_profile_${userId}`;

export function loadProfilePrefs(userId: string): ProfilePrefs {
  try {
    const parsed = JSON.parse(localStorage.getItem(key(userId)) || "{}");
    return parsed && typeof parsed === "object" ? (parsed as ProfilePrefs) : {};
  } catch {
    return {};
  }
}

export function saveProfilePrefs(userId: string, prefs: ProfilePrefs): boolean {
  try {
    localStorage.setItem(key(userId), JSON.stringify(prefs));
    return true;
  } catch {
    return false;
  }
}

export function fileToAvatar(file: File, size = 256): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith("image/")) {
      reject(new Error("Please choose an image file."));
      return;
    }
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const side = Math.min(img.width, img.height);
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        URL.revokeObjectURL(url);
        reject(new Error("Could not process the image."));
        return;
      }
      ctx.drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, size, size);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not read that image."));
    };
    img.src = url;
  });
}
