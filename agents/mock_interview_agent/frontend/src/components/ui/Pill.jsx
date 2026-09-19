import React from "react";

/**
 * Selectable pill control used for compact option sets.
 * @param {{ children: React.ReactNode, active?: boolean, warn?: boolean, onClick?: () => void, type?: "button" | "submit" | "reset" }} props
 */
export default function Pill({ children, active = false, warn = false, onClick, type = "button" }) {
  const classes = ["pill", active ? "pill-active" : "", warn ? "pill-warn" : ""]
    .filter(Boolean)
    .join(" ");

  if (!onClick) {
    return <span className={classes}>{children}</span>;
  }

  return (
    <button type={type} className={classes} onClick={onClick}>
      {children}
    </button>
  );
}
