import { useEffect, useState } from "react";
import {
  SKILL_CATEGORIES,
  categoriesToSkills,
  cleanBulletText,
  normalizeBulletList,
  normalizeSkillName,
  skillsToCategories,
} from "../utils/resumeContent.js";

export function SuggestionPanel({
  error = "",
  loading = false,
  onApply,
  onRegenerate,
  onReject,
  suggestions = [],
  title = "AI suggestions",
}) {
  const [edited, setEdited] = useState(() =>
    suggestions.map((item) => item.content || item.text || item),
  );

  useEffect(() => {
    setEdited(suggestions.map((item) => item.content || item.text || item));
  }, [suggestions]);

  if (loading) {
    return (
      <section className="suggestion-panel is-loading" role="status">
        <div className="suggestion-panel__shine" aria-hidden="true" />
        <h3>{title}</h3>
        <p>Generating reviewable suggestions...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="suggestion-panel error" role="alert">
        <h3>{title}</h3>
        <p>{error}</p>
        {onRegenerate && (
          <button className="secondary-button" onClick={onRegenerate} type="button">
            Retry
          </button>
        )}
      </section>
    );
  }

  if (!suggestions.length) return null;

  return (
    <section className="suggestion-panel">
      <div className="suggestion-panel__header">
        <div>
          <p className="eyebrow">AI generated content</p>
          <h3>{title}</h3>
        </div>
        {onRegenerate && (
          <button className="secondary-button" onClick={onRegenerate} type="button">
            Regenerate
          </button>
        )}
      </div>
      <div className="suggestion-list">
        {suggestions.map((item, index) => {
          const reason = item.reason || "Review and edit before applying.";
          return (
            <article className="suggestion-card" key={item.id || `${title}-${index}`}>
              <label>
                Suggestion
                <textarea
                  onChange={(event) =>
                    setEdited((current) =>
                      current.map((value, valueIndex) =>
                        valueIndex === index ? event.target.value : value,
                      ),
                    )
                  }
                  rows="3"
                  value={edited[index] ?? ""}
                />
              </label>
              <p>{reason}</p>
              <div className="suggestion-card__actions">
                <button className="primary-link" onClick={() => onApply?.(edited[index], index)} type="button">
                  Accept
                </button>
                <button className="secondary-button" onClick={() => onReject?.(index)} type="button">
                  Reject
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function BulletEditor({ bullets = [], onChange, title = "Approved bullets" }) {
  const cleanBullets = normalizeBulletList(bullets);

  function update(nextBullets) {
    onChange?.(normalizeBulletList(nextBullets));
  }

  return (
    <section className="bullet-editor">
      <div className="bullet-editor__header">
        <h3>{title}</h3>
        <button
          className="secondary-button compact-button"
          onClick={() => update([...cleanBullets, "Describe achievement, tool, and result."])}
          type="button"
        >
          Add bullet
        </button>
      </div>
      {cleanBullets.length === 0 ? (
        <p className="bullet-editor__empty">No approved bullets yet. Generate suggestions or add one manually.</p>
      ) : (
        <div className="bullet-editor__list">
          {cleanBullets.map((bullet, index) => (
            <article className="bullet-editor__row" key={`bullet-editor-${index}`}>
              <span aria-hidden="true">&bull;</span>
              <textarea
                onChange={(event) => {
                  const next = cleanBullets.map((item, itemIndex) =>
                    itemIndex === index ? cleanBulletText(event.target.value) : item,
                  );
                  update(next);
                }}
                rows="2"
                value={bullet}
              />
              <div className="bullet-editor__actions">
                <button
                  className="secondary-button compact-button"
                  disabled={index === 0}
                  onClick={() => {
                    const next = [...cleanBullets];
                    [next[index - 1], next[index]] = [next[index], next[index - 1]];
                    update(next);
                  }}
                  type="button"
                >
                  Up
                </button>
                <button
                  className="secondary-button compact-button"
                  disabled={index === cleanBullets.length - 1}
                  onClick={() => {
                    const next = [...cleanBullets];
                    [next[index], next[index + 1]] = [next[index + 1], next[index]];
                    update(next);
                  }}
                  type="button"
                >
                  Down
                </button>
                <button
                  className="danger-button compact-button"
                  onClick={() => update(cleanBullets.filter((_item, itemIndex) => itemIndex !== index))}
                  type="button"
                >
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export function SkillManager({ onChange, skills = [] }) {
  const [categories, setCategories] = useState(() => skillsToCategories(skills));
  const [drafts, setDrafts] = useState({});
  const [message, setMessage] = useState("");

  useEffect(() => {
    setCategories(skillsToCategories(skills));
  }, [skills]);

  function commit(nextCategories) {
    setCategories(nextCategories);
    onChange?.(categoriesToSkills(nextCategories));
  }

  function addSkill(category) {
    const skill = normalizeSkillName(drafts[category]);
    if (!skill) return;
    const duplicate = Object.values(categories)
      .flat()
      .some((item) => item.toLowerCase() === skill.toLowerCase());
    if (duplicate) {
      setMessage(`${skill} is already listed.`);
      return;
    }
    setMessage("");
    commit({ ...categories, [category]: [...categories[category], skill] });
    setDrafts((current) => ({ ...current, [category]: "" }));
  }

  function removeSkill(category, skill) {
    commit({
      ...categories,
      [category]: categories[category].filter((item) => item !== skill),
    });
  }

  return (
    <section className="skill-manager">
      <div className="skill-manager__header">
        <p className="eyebrow">Categorized skills</p>
        <p>Add skills as chips. Duplicates are blocked and saved in template-compatible categories.</p>
      </div>
      {message && <p className="status-message info">{message}</p>}
      <div className="skill-category-grid">
        {SKILL_CATEGORIES.map((category) => (
          <article className="skill-category-card" key={category}>
            <h3>{category}</h3>
            <div className="skill-chip-list">
              {categories[category].map((skill) => (
                <button key={skill} onClick={() => removeSkill(category, skill)} type="button" title={`Remove ${skill}`}>
                  <span aria-hidden="true">&bull;</span>
                  {skill}
                  <span aria-hidden="true">&times;</span>
                </button>
              ))}
            </div>
            <div className="skill-add-row">
              <input
                onChange={(event) => setDrafts((current) => ({ ...current, [category]: event.target.value }))}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    addSkill(category);
                  }
                }}
                placeholder="Add skill"
                value={drafts[category] ?? ""}
              />
              <button className="secondary-button compact-button" onClick={() => addSkill(category)} type="button">
                Add
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
