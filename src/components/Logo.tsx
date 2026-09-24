import React from "react";
import logoIcon from "../assets/logo-icon.svg";
import logoFull from "../assets/logo-full.svg";
import logoDark from "../assets/logo-dark.svg";
import logoMono from "../assets/logo-monochrome.svg";

export interface LogoProps {
  variant?: "full" | "icon" | "wordmark";
  theme?: "light" | "dark" | "monochrome";
  size?: "sm" | "md" | "lg" | number;
  className?: string;
  alt?: string;
}

export const Logo: React.FC<LogoProps> = ({
  variant = "full",
  theme = "light",
  size = "md",
  className = "",
  alt = "DigiDARA AI Resume",
}) => {
  let src = logoFull;
  if (variant === "icon") {
    src = logoIcon;
  } else if (theme === "dark") {
    src = logoDark;
  } else if (theme === "monochrome") {
    src = logoMono;
  }

  let height = 36;
  if (typeof size === "number") {
    height = size;
  } else if (size === "sm") {
    height = 28;
  } else if (size === "lg") {
    height = 44;
  }

  return (
    <img
      src={src}
      alt={alt}
      height={height}
      style={{ height: `${height}px`, width: "auto", display: "inline-block", verticalAlign: "middle" }}
      className={`brand-logo-img ${className}`.trim()}
    />
  );
};
