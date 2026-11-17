'use client';
import React from 'react';

export function CineBotFloatingTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label="Mở CineBot"
      className="comic-bot-trigger fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-40 hidden sm:flex min-h-[44px] min-w-[44px] items-center justify-center border border-surface-border bg-surface-elevated px-4 py-2.5 text-xs font-semibold text-ink transition-colors hover:border-brand hover:bg-surface-hover active:scale-95 cursor-pointer"
    >
      <span>Hỏi CineBot</span>
    </button>
  );
}
