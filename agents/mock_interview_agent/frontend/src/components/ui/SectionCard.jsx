import React from "react";

/**
 * Reusable full-width content panel.
 * @param {{ title?: string, subtitle?: string, className?: string, children: React.ReactNode, [key: string]: unknown }} props
 */
export default function SectionCard({
  title,
  subtitle,
  className = "",
  children,
  ...sectionProps
}) {
  return (
    <section className={`section-card ${className}`} {...sectionProps}>
      {(title || subtitle) && (
        <div className="section-card-header">
          {title && <h3>{title}</h3>}
          {subtitle && <p>{subtitle}</p>}
        </div>
      )}
      {children}
    </section>
  );
}
