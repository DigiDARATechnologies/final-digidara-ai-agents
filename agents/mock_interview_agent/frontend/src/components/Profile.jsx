import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  getProfile,
  removeProfileAvatar,
  updateProfile,
  uploadProfileAvatar,
} from "../api";
import PageHeader from "./ui/PageHeader";
import SectionCard from "./ui/SectionCard";
import Skeleton, { SkeletonStack } from "./ui/Skeleton";
import StatBox from "./ui/StatBox";
import StudentAvatar from "./ui/StudentAvatar";
import {
  ACTION_ICONS,
  PROFILE_FIELD_ICONS,
  STAT_ICONS,
} from "../utils/icons";
import { AVATAR_COLORS, getInitials } from "../utils/profile";
import { reportClientError } from "../utils/clientLogger";

const EditIcon = ACTION_ICONS.edit;
const SaveIcon = ACTION_ICONS.save;
const CancelIcon = ACTION_ICONS.cancel;
const CameraIcon = ACTION_ICONS.camera;
const RemoveIcon = ACTION_ICONS.remove;
const MAX_AVATAR_BYTES = 3 * 1024 * 1024;
const ALLOWED_AVATAR_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const CONTACT_FIELDS = [
  {
    name: "email",
    label: "Email",
    type: "email",
    placeholder: "Enter your email address",
    autoComplete: "email",
    maxLength: 150,
  },
  {
    name: "phone",
    label: "Phone",
    type: "tel",
    placeholder: "Enter your phone number",
    autoComplete: "tel",
    maxLength: 20,
  },
  {
    name: "course_enrolled",
    label: "Course Enrolled",
    type: "text",
    placeholder: "Enter your enrolled course",
    autoComplete: "off",
    maxLength: 150,
  },
  {
    name: "target_role",
    label: "Target Role",
    type: "text",
    placeholder: "Enter your target role",
    autoComplete: "organization-title",
    maxLength: 100,
  },
];

function toProfileForm(profileData = {}) {
  return {
    ...profileData,
    name: profileData.name ?? "",
    email: profileData.email ?? "",
    phone: profileData.phone ?? "",
    course_enrolled: profileData.course_enrolled ?? "",
    target_role: profileData.target_role ?? "",
    bio: profileData.bio ?? "",
  };
}

/**
 * Student profile display and edit screen.
 * @param {{ studentId: number, onProfileUpdate?: (profile: object) => void }} props
 */
export default function Profile({ studentId, onProfileUpdate }) {
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState({});
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [avatarPreview, setAvatarPreview] = useState(null);
  const avatarInputRef = useRef(null);

  useEffect(() => () => {
    if (avatarPreview) URL.revokeObjectURL(avatarPreview);
  }, [avatarPreview]);

  useEffect(() => {
    let isMounted = true;

    async function loadProfile() {
      await Promise.resolve();
      if (!isMounted) return;
      setLoading(true);
      setError(null);
      try {
        const data = await getProfile(studentId);
        if (!isMounted) return;
        setProfile(data);
        setForm(toProfileForm(data));
      } catch (requestError) {
        reportClientError("profile_load_failed", requestError, {
          student_id: studentId,
        });
        if (isMounted) {
          setError(
            requestError.message || "Unable to load profile. Please try again."
          );
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadProfile();

    return () => {
      isMounted = false;
    };
  }, [studentId]);

  const initials = useMemo(
    () => getInitials(profile?.name, profile?.email),
    [profile?.name, profile?.email]
  );

  function handleChange(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function handleEdit() {
    setForm(toProfileForm(profile));
    setSaveError(null);
    setEditing(true);
  }

  function handleCancel() {
    setForm(toProfileForm(profile));
    setSaveError(null);
    setEditing(false);
  }

  async function handleSave() {
    const name = (form.name || "").trim();
    const email = (form.email || "").trim();
    if (!name || !email) {
      setSaveError("Name and email are required.");
      return;
    }

    setSaving(true);
    setSaveError(null);

    try {
      const payload = {
        name,
        email,
        phone: form.phone || "",
        course_enrolled: form.course_enrolled || "",
        target_role: form.target_role || "",
        bio: form.bio || "",
        avatar_color: form.avatar_color || AVATAR_COLORS[0],
      };
      const updated = await updateProfile(studentId, payload);
      setProfile(updated);
      setForm(toProfileForm(updated));
      setEditing(false);
      onProfileUpdate?.(updated);
    } catch (e) {
      reportClientError("profile_save_failed", e, { student_id: studentId });
      setSaveError(e.message || "Could not save profile. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function applyAvatarProfile(updated) {
    setProfile(updated);
    setForm((currentForm) => ({
      ...updated,
      ...currentForm,
      avatar_url: updated.avatar_url,
    }));
    onProfileUpdate?.(updated);
  }

  async function handleAvatarSelected(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setSaveError(null);
    if (!ALLOWED_AVATAR_TYPES.has(file.type)) {
      setSaveError("Choose a JPG, JPEG, PNG, or WebP image.");
      return;
    }
    if (file.size > MAX_AVATAR_BYTES) {
      setSaveError("Profile photos must be 3 MB or smaller.");
      return;
    }

    setAvatarPreview(URL.createObjectURL(file));
    setUploadingAvatar(true);
    try {
      const updated = await uploadProfileAvatar(studentId, file);
      applyAvatarProfile(updated);
    } catch (e) {
      reportClientError("profile_avatar_upload_failed", e, { student_id: studentId });
      setSaveError(e.message || "Could not upload profile photo.");
    } finally {
      setUploadingAvatar(false);
      setAvatarPreview(null);
    }
  }

  async function handleRemoveAvatar() {
    setUploadingAvatar(true);
    setSaveError(null);
    try {
      const updated = await removeProfileAvatar(studentId);
      applyAvatarProfile(updated);
    } catch (e) {
      reportClientError("profile_avatar_remove_failed", e, { student_id: studentId });
      setSaveError(e.message || "Could not remove profile photo.");
    } finally {
      setUploadingAvatar(false);
    }
  }

  if (loading) {
    return (
      <div className="page profile-page">
        <PageHeader
          eyebrow="Student"
          title="Profile"
          description="Manage your interview profile and performance summary."
        />
        <SectionCard>
          <Skeleton className="profile-hero-skeleton" />
          <SkeletonStack rows={3} />
        </SectionCard>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page profile-page">
        <PageHeader eyebrow="Student" title="Profile" />
        <SectionCard>
          <p className="error-text" role="alert">{error}</p>
        </SectionCard>
      </div>
    );
  }

  const avatarColor = form.avatar_color || profile.avatar_color || AVATAR_COLORS[0];

  return (
    <div className="page profile-page">
      <PageHeader
        eyebrow="Student"
        title="Profile"
        description="Keep your student details updated for personalized interview practice."
      />

      <section className="profile-hero section-card">
        <div className="profile-avatar-wrap">
          <StudentAvatar
            className="profile-avatar"
            avatarUrl={avatarPreview || profile.avatar_url}
            initials={initials}
            avatarColor={avatarColor}
          />
          {editing && (
            <>
              <input
                ref={avatarInputRef}
                className="avatar-file-input"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleAvatarSelected}
              />
              <div className="avatar-upload-controls">
                <button
                  type="button"
                  className="avatar-photo-btn avatar-upload-btn"
                  onClick={() => avatarInputRef.current?.click()}
                  disabled={uploadingAvatar || saving}
                >
                  <CameraIcon size={16} strokeWidth={2} aria-hidden="true" />
                  {uploadingAvatar ? "Updating..." : profile.avatar_url ? "Change Photo" : "Upload Photo"}
                </button>
                {profile.avatar_url && (
                  <button
                    type="button"
                    className="avatar-photo-btn avatar-remove-btn"
                    onClick={handleRemoveAvatar}
                    disabled={uploadingAvatar || saving}
                  >
                    <RemoveIcon size={16} strokeWidth={2} aria-hidden="true" />
                    Remove
                  </button>
                )}
              </div>
              <span className="avatar-upload-hint">JPG, PNG or WebP · max 3 MB</span>
              <div className="avatar-color-row" aria-label="Choose avatar fallback color">
                {AVATAR_COLORS.map((color) => (
                  <button
                    key={color}
                    type="button"
                    className={`avatar-color-dot ${avatarColor === color ? "avatar-color-active" : ""}`}
                    style={{ backgroundColor: color }}
                    aria-label={`Use avatar color ${color}`}
                    onClick={() => handleChange("avatar_color", color)}
                  />
                ))}
              </div>
            </>
          )}
        </div>

        <div className="profile-hero-copy">
          {editing ? (
            <div className="profile-edit-grid">
              <label>
                <span>Name</span>
                <input
                  name="name"
                  required
                  value={form.name || ""}
                  onChange={(e) => handleChange("name", e.target.value)}
                />
              </label>
              <label>
                <span>Email</span>
                <input
                  name="email"
                  type="email"
                  required
                  value={form.email || ""}
                  onChange={(e) => handleChange("email", e.target.value)}
                />
              </label>
            </div>
          ) : (
            <>
              <h2>{profile.name || "Student"}</h2>
              <p>{profile.target_role || "Target role not set"}</p>
            </>
          )}
        </div>

        <div className="profile-actions">
          {editing ? (
            <>
              <button className="secondary-btn" onClick={handleCancel} disabled={saving || uploadingAvatar}>
                <CancelIcon className="profile-icon" size={18} strokeWidth={2} /> Cancel
              </button>
              <button className="primary-btn" onClick={handleSave} disabled={saving || uploadingAvatar}>
                <SaveIcon className="profile-icon" size={18} strokeWidth={2} /> {saving ? "Saving..." : "Save Profile"}
              </button>
            </>
          ) : (
            <button className="primary-btn" onClick={handleEdit}>
              <EditIcon className="profile-icon" size={18} strokeWidth={2} /> Edit Profile
            </button>
          )}
        </div>
      </section>

      {saveError && <p className="error-text" role="alert">{saveError}</p>}

      <div className="stat-grid profile-stat-grid">
        <StatBox icon={STAT_ICONS.totalInterviews} value={profile.total_interviews ?? 0} label="Total Interviews" />
        <StatBox icon={STAT_ICONS.averageScore} value={profile.average_score ?? "-"} label="Average Score" unit="/10" />
        <StatBox icon={STAT_ICONS.technicalRounds} value={profile.technical_interviews_count ?? 0} label="Technical Rounds" />
        <StatBox icon={STAT_ICONS.hrRounds} value={profile.hr_interviews_count ?? 0} label="HR Rounds" />
      </div>

      <div className="profile-content-grid">
        <SectionCard className="profile-contact-card" title="Contact Details" subtitle="Basic student and academic information.">
          <div className="profile-field-list">
            {CONTACT_FIELDS.map(({ name, label, ...inputProps }) => {
              const FieldIcon = PROFILE_FIELD_ICONS[name];
              return (
                <label key={name} className="profile-field" htmlFor={`profile-${name}`}>
                  <span className="profile-field-label">
                    <FieldIcon className="profile-icon" size={18} strokeWidth={2} /> {label}
                  </span>
                  {editing ? (
                    <input
                      id={`profile-${name}`}
                      name={name}
                      value={form[name] ?? ""}
                      onChange={(e) => handleChange(e.target.name, e.target.value)}
                      disabled={saving}
                      {...inputProps}
                    />
                  ) : (
                    <strong>{profile[name] || "Not provided"}</strong>
                  )}
                </label>
              );
            })}
          </div>
        </SectionCard>

        <SectionCard className="profile-bio-card" title="Bio" subtitle="A short introduction for your interview profile.">
          {editing ? (
            <textarea
              className="profile-bio-input"
              value={form.bio || ""}
              onChange={(e) => handleChange("bio", e.target.value)}
              rows={8}
            />
          ) : (
            <p className="profile-bio-text">{profile.bio || "No bio added yet."}</p>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
