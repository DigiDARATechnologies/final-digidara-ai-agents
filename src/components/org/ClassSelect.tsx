import { useState } from "react";

const ADD_NEW = "__add_new__";

interface Props {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  /** Optional fields show "Not set"; required ones would not. */
  placeholder?: string;
  disabled?: boolean;
  maxLength?: number;
}

/** A dropdown whose last choice is "+ Add new…": picking it opens a box for
 * a new department, year or section, which then becomes the selection. */
export default function ClassSelect({ label, value, options, onChange, placeholder = "Not set", disabled, maxLength = 120 }: Props) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");
  const choices = value && !options.some((o) => o.toLowerCase() === value.toLowerCase()) ? [...options, value] : options;

  function confirm() {
    const clean = draft.trim().replace(/\s+/g, " ").slice(0, maxLength);
    if (clean) onChange(clean);
    setDraft("");
    setAdding(false);
  }

  return (
    <label className="field org-class-select">
      <span>{label} <small>(optional)</small></span>
      {adding ? (
        <div className="org-add-new">
          <input autoFocus value={draft} maxLength={maxLength} placeholder={`New ${label.toLowerCase()}`}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { e.preventDefault(); confirm(); }
              if (e.key === "Escape") { setAdding(false); setDraft(""); }
            }} />
          <button type="button" className="btn btn-primary btn-sm" onClick={confirm} disabled={!draft.trim()}>Add</button>
          <button type="button" className="link-btn" onClick={() => { setAdding(false); setDraft(""); }}>Cancel</button>
        </div>
      ) : (
        <select value={value} disabled={disabled} onChange={(e) => {
          if (e.target.value === ADD_NEW) setAdding(true);
          else onChange(e.target.value);
        }}>
          <option value="">{placeholder}</option>
          {choices.map((option) => <option key={option} value={option}>{option}</option>)}
          <option value={ADD_NEW}>+ Add new…</option>
        </select>
      )}
    </label>
  );
}
