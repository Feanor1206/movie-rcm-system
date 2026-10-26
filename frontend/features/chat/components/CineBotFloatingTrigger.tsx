'use client';
import React from 'react';

/**
 * Floating Trigger Button for CineBot (Clean rectangular design, accessible 44px touch target)
 */
export function CineBotFloatingTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label="Mở Chatbot CineBot"
      className="comic-bot-trigger fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-40 flex min-h-[44px] min-w-[44px] items-center gap-2 rounded-full sm:rounded-md border border-surface-border bg-surface px-3.5 py-2.5 sm:px-4 text-xs font-semibold text-ink shadow-lg transition hover:border-brand hover:bg-surface-muted cursor-pointer"
    >
      <span className="h-2.5 w-2.5 rounded-full bg-brand shadow-brand-sm" />
      <span>Hỏi CineBot</span>
    </button>
  );
}
