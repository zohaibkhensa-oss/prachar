import Image from "next/image";

interface LogoProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  href?: string;
}

const SIZES = {
  sm: { width: 120, height: 60 },
  md: { width: 180, height: 90 },
  lg: { width: 280, height: 140 },
};

export function Logo({ size = "md", className = "", href }: LogoProps) {
  const dims = SIZES[size];
  const img = (
    <Image
      src="/prachar-logo.png"
      alt="PRACHAR"
      width={dims.width}
      height={dims.height}
      className={`object-contain ${className}`}
      priority
    />
  );
  if (href) {
    return (
      <a href={href} className="inline-block">
        {img}
      </a>
    );
  }
  return img;
}
