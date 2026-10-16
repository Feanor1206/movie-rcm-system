'use client';

import React, { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import {
  X,
  Send,
  Star,
  Bookmark,
  Check,
  Play,
  RotateCcw,
} from 'lucide-react';
import { sendChatMessage, ChatMessage } from '@/lib/services/chatService';
import { useWatchlist } from '@/lib/context/WatchlistContext';
import type { Movie } from '@/types/movie';

const QUICK_PROMPTS = [
  'Spirited Away',
  'Hoạt hình sau 2000',
  'Trước năm 2015',
  'Sci-Fi vũ trụ',
  'Điểm cao nhất',
];

const BDG = 'rounded bg-zinc-900 border px-1.5 py-0.5 text-[10px]';
const BTN_HEAD = 'flex h-11 w-11 min-h-[44px] min-w-[44px] items-center justify-center rounded-md text-zinc-400 hover:bg-zinc-800 hover:text-white cursor-pointer';

export function CineBot({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { isWatchlisted, toggleWatchlist } = useWatchlist();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'bot',
      text: 'Xin chào! Tôi là CineBot, trợ lý gợi ý phim hoạt hình Dippie.',
      timestamp: 'Vừa xong',
      followUps: QUICK_PROMPTS.slice(0, 3),
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const cinebotRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  const scrollToBottom = () => {
    const isReduced =
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    messagesEndRef.current?.scrollIntoView({ behavior: isReduced ? 'auto' : 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  // A11y: Escape key, body scroll lock, focus trap, and initial focus
  useEffect(() => {
    if (!isOpen) return;

    // Save previous active element to restore focus upon closing (only if outside dialog)
    if (document.activeElement && (!cinebotRef.current || !cinebotRef.current.contains(document.activeElement))) {
      openerRef.current = document.activeElement as HTMLElement | null;
    }

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const timer = setTimeout(() => {
      inputRef.current?.focus();
    }, 50);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === 'Tab' && cinebotRef.current) {
        const focusable = cinebotRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (!cinebotRef.current.contains(document.activeElement)) {
          e.preventDefault();
          if (e.shiftKey) last.focus();
          else first.focus();
          return;
        }

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      clearTimeout(timer);
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
      openerRef.current?.focus();
    };
  }, [isOpen, onClose]);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setInput('');
    setIsTyping(true);

    try {
      // Gửi câu hỏi đến /api/chat (nơi bạn có thể cắm model Python / FastAPI / LLM)
      const result = await sendChatMessage(text, nextMessages);

      const botMessage: ChatMessage = {
        id: `bot-${Date.now()}`,
        sender: 'bot',
        text: result.text,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        movies: result.recommendedMovies,
        followUps: result.followUps,
        structuredIntent: result.structuredIntent,
        pipelineStages: result.pipelineStages,
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (err: any) {
      console.error('Lỗi nhận phản hồi:', err);
      const errorMsg: ChatMessage = {
        id: `bot-err-${Date.now()}`,
        sender: 'bot',
        text: `⚠️ ${err?.message || 'Lỗi kết nối AI Gateway. Thử lại sau.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  };

  const resetChat = () => {
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        sender: 'bot',
        text: 'Cuộc trò chuyện đã làm mới.',
        timestamp: 'Vừa xong',
        followUps: QUICK_PROMPTS.slice(0, 3),
      },
    ]);
  };

  if (!isOpen) return null;

  return (
    <div
      ref={cinebotRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="cinebot-dialog-title"
      className="fixed inset-0 z-50 flex items-end justify-end p-0 sm:p-6 bg-black/60 backdrop-blur-sm animate-fade-in pointer-events-auto"
    >
      <div className="flex h-full w-full flex-col overflow-hidden bg-surface border-0 sm:border sm:border-surface-border sm:rounded-xl sm:h-[620px] sm:w-[440px] sm:shadow-2xl">
        {/* Chatbot Header */}
        <div className="flex items-center justify-between border-b border-surface-border bg-surface-muted px-4 py-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 id="cinebot-dialog-title" className="text-sm font-bold text-white">
                CineBot
              </h2>
              <span className="rounded bg-brand/15 border border-brand/30 px-1.5 py-0.5 text-[10px] text-brand font-semibold">
                Trợ lý Dippie
              </span>
            </div>
            <p className="text-[11px] text-zinc-400">Gợi ý phim hoạt hình</p>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={resetChat}
              title="Làm mới"
              aria-label="Làm mới cuộc trò chuyện"
              className={BTN_HEAD}
            >
              <RotateCcw size={16} />
            </button>
            <button
              onClick={onClose}
              title="Đóng"
              aria-label="Đóng CineBot"
              className={BTN_HEAD}
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Message Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
            >
              {/* Message Box */}
              <div
                className={`max-w-[90%] rounded-lg px-3.5 py-2.5 text-xs sm:text-sm leading-relaxed ${
                  msg.sender === 'user'
                    ? 'bg-brand text-zinc-950 font-medium shadow-brand-sm'
                    : 'bg-surface-muted text-zinc-100 border border-surface-border'
                }`}
              >
                <p>{msg.text}</p>
                <span
                  className={`mt-1 block text-[10px] ${
                    msg.sender === 'user' ? 'text-zinc-950/70 text-right font-medium' : 'text-zinc-500'
                  }`}
                >
                  {msg.timestamp}
                </span>
              </div>

              {/* Phase 23 Structured Intent Badges */}
              {msg.sender === 'bot' && msg.structuredIntent && (
                <div className="mt-1.5 flex flex-wrap gap-1 max-w-[95%]">
                  <span className={`${BDG} border-zinc-700 font-mono text-emerald-400`}>
                    {msg.structuredIntent.intent_type}
                  </span>
                  {msg.structuredIntent.reference_films && msg.structuredIntent.reference_films.length > 0 && (
                    <span className={`${BDG} border-zinc-800 text-amber-300`}>
                      Ref: {msg.structuredIntent.reference_films.join(', ')}
                    </span>
                  )}
                  {msg.structuredIntent.include_genres && msg.structuredIntent.include_genres.length > 0 && (
                    <span className={`${BDG} border-zinc-800 text-sky-300`}>
                      +{msg.structuredIntent.include_genres.join(', ')}
                    </span>
                  )}
                  {msg.structuredIntent.exclude_genres && msg.structuredIntent.exclude_genres.length > 0 && (
                    <span className={`${BDG} border-red-900/60 text-rose-400`}>
                      -{msg.structuredIntent.exclude_genres.join(', ')}
                    </span>
                  )}
                  {(msg.structuredIntent.year_min || msg.structuredIntent.year_max) && (
                    <span className={`${BDG} border-zinc-800 text-purple-300`}>
                      Năm: {msg.structuredIntent.year_min || '…'}–{msg.structuredIntent.year_max || 'nay'}
                    </span>
                  )}
                  {msg.structuredIntent.requested_k && (
                    <span className={`${BDG} border-zinc-800 text-zinc-400`}>
                      Top {msg.structuredIntent.requested_k}
                    </span>
                  )}
                </div>
              )}

              {/* Embedded Interactive Movie Cards */}
              {msg.movies && msg.movies.length > 0 && (
                <div className="mt-2.5 w-full space-y-2">
                  {msg.movies.map((movie) => {
                    const inWatchlist = isWatchlisted(movie.id);
                    return (
                      <div
                        key={movie.id}
                        className="flex gap-3 rounded-lg border border-surface-border bg-surface-muted p-2.5 transition-colors hover:border-zinc-700"
                      >
                        {/* Poster */}
                        <div className="relative h-20 w-14 shrink-0 overflow-hidden rounded border border-surface-border bg-surface">
                          <Image
                            src={movie.poster}
                            alt={movie.title}
                            fill
                            className="object-cover"
                            sizes="56px"
                          />
                        </div>

                        {/* Details */}
                        <div className="flex flex-col justify-between flex-1 min-w-0">
                          <div>
                            <div className="flex items-center justify-between gap-1">
                              <Link
                                href={`/movies/${movie.id}`}
                                onClick={onClose}
                                className="truncate text-xs sm:text-sm font-semibold text-white hover:text-brand transition-colors"
                              >
                                {movie.title}
                              </Link>
                              <span className="flex items-center gap-0.5 text-[11px] font-bold text-amber-400 shrink-0">
                                <Star size={11} className="fill-amber-400" /> {movie.rating}
                              </span>
                            </div>
                            <p className="text-[11px] text-zinc-400 mt-0.5">
                              {movie.year} · {movie.runtime} · {movie.genres.join(', ')}
                            </p>
                          </div>

                          {/* Quick Actions */}
                          <div className="mt-2 flex items-center gap-2">
                            <Link
                              href={`/movies/${movie.id}`}
                              onClick={onClose}
                              className="inline-flex items-center gap-1 rounded bg-brand px-2 py-0.5 text-[10px] font-bold text-zinc-950 hover:bg-brand-hover shadow-brand-sm cursor-pointer"
                            >
                              <Play size={10} className="fill-current" /> Xem chi tiết
                            </Link>

                            <button
                              onClick={() => toggleWatchlist(movie.id, movie.title)}
                              className="inline-flex items-center gap-1 rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5 text-[10px] font-medium text-zinc-200 hover:border-zinc-500 hover:text-white cursor-pointer"
                            >
                              {inWatchlist ? (
                                <>
                                  <Check size={10} className="text-brand" /> Đã lưu
                                </>
                              ) : (
                                '+ Watchlist'
                              )}
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Follow-up Suggestions (Clean rectangular buttons, No pills) */}
              {msg.followUps && msg.followUps.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {msg.followUps.map((prompt) => (
                    <button
                      key={prompt}
                      disabled={isTyping}
                      onClick={() => handleSend(prompt)}
                      className="rounded border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-[11px] text-zinc-300 transition-colors hover:border-zinc-600 hover:text-white cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* Typing indicator */}
          {isTyping && (
            <div className="flex items-center gap-2 text-xs text-zinc-300 bg-surface-muted border border-brand/40 rounded-md px-3 py-1.5 w-fit">
              <span className="flex gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-brand animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="h-1.5 w-1.5 rounded-full bg-brand animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="h-1.5 w-1.5 rounded-full bg-brand animate-bounce" style={{ animationDelay: '300ms' }} />
              </span>
              <span>CineBot đang suy luận...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="border-t border-surface-border bg-surface-muted p-3">
          <div className="flex items-center gap-2 rounded-md border border-surface-border bg-surface px-3 py-2 focus-within:border-brand">
            <input
              ref={inputRef}
              type="text"
              value={input}
              disabled={isTyping}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isTyping ? "CineBot đang phản hồi..." : "Nhập câu hỏi..."}
              className="w-full bg-transparent text-xs sm:text-sm text-white placeholder:text-zinc-500 focus:outline-none disabled:opacity-60"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isTyping}
              className="grid h-7 w-7 place-items-center rounded bg-brand text-zinc-950 transition hover:bg-brand-hover shadow-brand-sm disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              aria-label="Gửi tin nhắn"
            >
              <Send size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Floating Trigger Button for CineBot (Clean rectangular design, accessible 44px touch target)
 */
export function CineBotFloatingTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label="Mở Chatbot CineBot"
      className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-40 flex min-h-[44px] min-w-[44px] items-center gap-2 rounded-full sm:rounded-md border border-surface-border bg-surface px-3.5 py-2.5 sm:px-4 text-xs font-semibold text-white shadow-lg transition hover:border-brand hover:bg-surface-muted cursor-pointer"
    >
      <span className="h-2.5 w-2.5 rounded-full bg-brand shadow-brand-sm" />
      <span>Hỏi CineBot</span>
    </button>
  );
}
