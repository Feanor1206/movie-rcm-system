'use client';
import React from 'react';

export function CineBotFloatingTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label="Mở CineBot"
      className="comic-bot-trigger fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-40 flex min-h-[44px] min-w-[44px] items-center gap-2 rounded-full sm:rounded-md border border-surface-border bg-surface px-3.5 py-2.5 sm:px-4 text-xs font-semibold text-ink shadow-lg transition hover:border-brand hover:bg-surface-muted cursor-pointer"
    >
      <span>Hỏi CineBot</span>
    </button>
  );
}
