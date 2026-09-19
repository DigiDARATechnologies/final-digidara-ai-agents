import React from "react";

/**
 * Shimmer placeholder block for loading states.
 * @param {{ className?: string }} props
 */
export default function Skeleton({ className = "" }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

/**
 * Card-shaped skeleton layout used by list and dashboard screens.
 * @param {{ rows?: number }} props
 */
export function SkeletonStack({ rows = 3 }) {
  return (
    <div className="skeleton-stack" aria-label="Loading">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton-row">
          <Skeleton className="skeleton-dot" />
          <div className="skeleton-copy">
            <Skeleton className="skeleton-line skeleton-line-wide" />
            <Skeleton className="skeleton-line skeleton-line-short" />
          </div>
        </div>
      ))}
    </div>
  );
}
