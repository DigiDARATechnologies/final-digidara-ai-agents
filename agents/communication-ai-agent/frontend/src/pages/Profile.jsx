import { useEffect, useRef, useState } from "react";
import client from "../api/client";
import { useAuth } from "../context/AuthContext.jsx";

const API_ORIGIN = (client.defaults.baseURL || "").replace(/\/api\/?$/, "");

function photoSrc(url) {
  if (!url) return null;
  if (url.startsWith("blob:") || url.startsWith("data:") || url.startsWith("http")) return url;
  return `${API_ORIGIN}${url}`;
}

export default function Profile() {
  const { user, refreshUser } = useAuth();
  const fileInputRef = useRef(null);
  const [name, setName] = useState(user?.name || "");
  const [email, setEmail] = useState(user?.email || "");
  const [phone, setPhone] = useState(user?.phone || "");
  const [courseName, setCourseName] = useState(user?.course_name || "");
  const [photoFile, setPhotoFile] = useState(null);
  const [photoPreview, setPhotoPreview] = useState(user?.photo_url || null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setName(user?.name || "");
    setEmail(user?.email || "");
    setPhone(user?.phone || "");
    setCourseName(user?.course_name || "");
    setPhotoPreview(user?.photo_url || null);
  }, [user]);

  useEffect(() => () => {
    if (photoPreview?.startsWith("blob:")) URL.revokeObjectURL(photoPreview);
  }, [photoPreview]);

  const choosePhoto = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!/^image\/(jpeg|png)$/.test(file.type)) {
      setError("Please choose a JPG or PNG photo.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("Photo must be 5 MB or smaller.");
      return;
    }
    setError("");
    setPhotoFile(file);
    setPhotoPreview(URL.createObjectURL(file));
  };

  const save = async (e) => {
    e.preventDefault();
    setError("");
    setMessage("");
    setSaving(true);
    let photoError = "";
    let profileError = "";

    if (photoFile) {
      try {
        const formData = new FormData();
        formData.append("photo", photoFile);
        await client.post("/profile/photo", formData);
      } catch (err) {
        photoError = err.response?.data?.message || "Photo upload failed.";
      }
    }

    try {
      await client.put("/profile", { name, email, phone, course_name: courseName });
    } catch (err) {
      profileError = err.response?.data?.message || "Could not update profile details.";
    }

    try {
      await refreshUser();
    } catch {
      if (!profileError) profileError = "Saved, but the updated profile could not be loaded.";
    }

    setPhotoFile(null);
    setSaving(false);
    if (photoError || profileError) {
      setError([photoError, profileError].filter(Boolean).join(" "));
    } else {
      setMessage("Profile updated successfully.");
    }
  };

  const avatarUrl = photoSrc(photoPreview);

  return (
    <div className="mx-auto max-w-2xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <h1 className="text-2xl font-bold text-slate-900">Profile</h1>
      <p className="mt-1 text-sm text-slate-500">Keep your learner details up to date.</p>

      <div className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 sm:p-7">
        <div className="mb-7 flex items-center gap-4">
          <div className="relative shrink-0">
            <div className="flex h-20 w-20 items-center justify-center overflow-hidden rounded-full bg-brand-100 text-2xl font-bold text-brand-700 ring-4 ring-brand-50">
              {avatarUrl ? <img src={avatarUrl} alt="Profile" className="h-full w-full object-cover" /> : user?.name?.[0]?.toUpperCase()}
            </div>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              aria-label="Upload profile photo"
              className="absolute bottom-0 right-0 flex h-8 w-8 items-center justify-center rounded-full border-2 border-white bg-brand-600 text-white shadow-md transition hover:bg-brand-700"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 7h3l1.5-2h7L17 7h3v11H4z" /><circle cx="12" cy="13" r="3" /></svg>
            </button>
            <input ref={fileInputRef} type="file" accept="image/jpeg,image/png" onChange={choosePhoto} className="hidden" />
          </div>
          <div className="min-w-0">
            <p className="text-base font-bold text-slate-800">{user?.name || "Your profile"}</p>
            <p className="mt-1 break-words text-xs text-slate-400">JPG or PNG, up to 5 MB</p>
          </div>
        </div>

        <form onSubmit={save} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-500">Full name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} className="min-h-10 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100" />
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-500">Email address</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={160} className="min-h-10 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100" />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-500">Phone number</label>
              <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} maxLength={30} placeholder="Add your phone number" className="min-h-10 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-500">Course name</label>
              <input value={courseName} onChange={(e) => setCourseName(e.target.value)} maxLength={120} placeholder="e.g. Professional English" className="min-h-10 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100" />
            </div>
          </div>

          {message && <p className="text-sm font-medium text-green-600">{message}</p>}
          {error && <p className="text-sm font-medium text-red-500">{error}</p>}
          <button type="submit" disabled={saving} className="w-full rounded-xl bg-brand-600 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-60">{saving ? "Saving…" : "Save changes"}</button>
        </form>
      </div>
    </div>
  );
}
