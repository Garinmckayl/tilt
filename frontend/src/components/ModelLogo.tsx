"use client";

import React from "react";

interface ModelLogoProps {
  family: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function ModelLogo({ family, size = "md", className = "" }: ModelLogoProps) {
  const dims =
    size === "sm"
      ? "w-6 h-6 text-xs"
      : size === "lg"
      ? "w-10 h-10 text-base"
      : "w-8 h-8 text-sm";

  if (family === "claude") {
    return (
      <div
        className={`${dims} rounded-full flex items-center justify-center font-serif font-bold tracking-tight border border-[#E6B8A2] bg-[#FDF3EE] text-[#C85A32] shadow-sm shrink-0 ${className}`}
        title="Anthropic Claude Sonnet 4.5"
      >
        <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current" aria-hidden="true">
          <path d="M12 2L14.2 8.8L21 9.5L15.7 13.8L17.5 20.5L12 16.7L6.5 20.5L8.3 13.8L3 9.5L9.8 8.8L12 2Z" />
        </svg>
      </div>
    );
  }

  if (family === "llama") {
    return (
      <div
        className={`${dims} rounded-full flex items-center justify-center font-sans font-bold tracking-tight border border-[#BFDBFE] bg-[#EFF6FF] text-[#1D4ED8] shadow-sm shrink-0 ${className}`}
        title="Meta Llama 3.3 70B"
      >
        <svg viewBox="0 0 24 24" className="w-4 h-4 fill-none stroke-current stroke-[2.2]" aria-hidden="true">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M4 15.5C4 11.5 6.8 8.5 9.5 8.5C11.2 8.5 12.6 9.8 14.5 12.5C16.2 14.9 17.5 15.5 18.8 15.5C20.2 15.5 21 13.8 21 12C21 9.8 19.6 8.5 18 8.5C16.3 8.5 14.8 10 12.8 12.8C10.9 15.3 9.5 16 7.8 16C5.6 16 4 14.2 4 12"
          />
        </svg>
      </div>
    );
  }

  return (
    <div
      className={`${dims} rounded-full flex items-center justify-center font-mono font-bold tracking-tight border border-[#99F6E4] bg-[#F0FDFA] text-[#0F766E] shadow-sm shrink-0 ${className}`}
      title="DeepSeek V3.2"
    >
      <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current" aria-hidden="true">
        <path d="M12 3C7.03 3 3 7.03 3 12C3 16.97 7.03 21 12 21C15.95 21 19.31 18.45 20.52 14.91C18.67 16.22 16.24 16.65 13.95 15.88C11.16 14.94 9.28 12.31 9.28 9.37C9.28 7.04 10.45 4.98 12.24 3.74C12.16 3.25 12.08 3 12 3Z" />
      </svg>
    </div>
  );
}
