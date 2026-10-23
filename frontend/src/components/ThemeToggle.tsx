import React from "react";
import { useTheme } from "../lib/useTheme";

export const ThemeToggle: React.FC<{ className?: string }> = ({ className = "" }) => {
  const [theme, toggle] = useTheme();
  return (
    <button
      onClick={toggle}
      className={`theme-toggle ${className}`}
      aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
      title={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
    >
      {theme === "light" ? "Dark" : "Light"}
    </button>
  );
};
