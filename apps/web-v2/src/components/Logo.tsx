"use client";

import { CurvMark } from "./CurvMark";

interface LogoProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  href?: string;
}

const SIZES = {
  sm: 28,
  md: 36,
  lg: 48,
};

export function Logo({ size = "md", className = "", href }: LogoProps) {
  const px = SIZES[size];
  const logo = (
    <CurvMark size={px} variant="full" className={className} />
  );
  if (href) {
    return (
      <a href={href} className="inline-flex">
        {logo}
      </a>
    );
  }
  return logo;
}
