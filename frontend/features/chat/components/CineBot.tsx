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
  Sparkles,
  Bot,
  User,
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

const BDG = 'rounded-md border px-2 py-0.5 text-[10px] font-medium backdrop-blur-sm';
const BTN_HEAD =
  'flex h-11 w-11 min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-zinc-400 hover:bg-surface-hover hover:text-white transition-colors cursor-pointer';

export function CineBot({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { isWatchlisted, toggleWatchlist } = useWatchlist();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'bot',
      text: 'Xin chào! Tôi là CineBot, trợ lý AI thông minh gợi ý phim hoạt hình Dippie. Bạn muốn tìm phim theo thể loại, cảm xúc hay thời kỳ nào?',
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
    if (
      document.activeElement &&
      (!cinebotRef.current || !cinebotRef.current.contains(document.activeElement))
    ) {
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
        text: 'Cuộc trò chuyện đã được làm mới. Tôi có thể giúp gì cho bạn?',
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
      className="fixed inset-0 z-50 flex items-end justify-end p-0 sm:p-6 bg-black/70 backdrop-blur-sm animate-fade-in pointer-events-auto"
    >
      <div className="flex h-full w-full flex-col overflow-hidden bg-surface border-0 sm:border sm:border-surface-border/90 sm:rounded-2xl sm:h-[650px] sm:w-[450px] sm:shadow-[0_20px_60px_rgba(0,0,0,0.9),0_0_35px_rgba(16,185,129,0.18)]">
        {/* Chatbot Header */}
        <div className="flex items-center justify-between border-b border-surface-border/80 bg-gradient-to-r from-surface-elevated via-surface to-surface-elevated px-4 py-3.5">
          <div className="flex items-center gap-3">
            <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand/20 to-brand/5 border border-brand/40 shadow-brand-sm">
              <Sparkles size={18} className="text-brand animate-pulse" />
              <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-400 ring-2 ring-surface" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 id="cinebot-dialog-title" className="text-sm font-extrabold text-white tracking-tight">
                  CineBot AI
                </h2>
                <span className="rounded-full bg-brand/15 border border-brand/35 px-2 py-0.2 text-[10px] text-brand font-bold">
                  Online
                </span>
              </div>
              <p className="text-[11px] text-zinc-400">Trợ lý gợi ý phim hoạt hình Dippie</p>
            </div>
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
        <div className="flex-1 overflow-y-auto p-4 space-y-4.5 bg-gradient-to-b from-surface via-background/60 to-surface">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
            >
              {/* Message Box with Asymmetric Corners */}
              <div className="flex items-start gap-2 max-w-[92%]">
                {msg.sender === 'bot' && (
                  <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface-elevated border border-brand/30 text-brand shadow-sm">
                    <Bot size={14} />
                  </div>
                )}

                <div
                  className={`rounded-2xl px-4 py-2.5 text-xs sm:text-sm leading-relaxed transition-all ${
                    msg.sender === 'user'
                      ? 'rounded-tr-xs bg-gradient-to-r from-emerald-500 to-teal-400 text-zinc-950 font-semibold shadow-[0_4px_16px_rgba(16,185,129,0.35)]'
                      : 'rounded-tl-xs bg-surface-elevated/95 text-zinc-100 border border-white/10 shadow-md backdrop-blur-md'
                  }`}
                >
                  <p>{msg.text}</p>
                  <span
                    className={`mt-1.5 block text-[10px] ${
                      msg.sender === 'user'
                        ? 'text-zinc-950/75 text-right font-medium'
                        : 'text-zinc-400'
                    }`}
                  >
                    {msg.timestamp}
                  </span>
                </div>
              </div>

              {/* Phase 23 Structured Intent Badges */}
              {msg.sender === 'bot' && msg.structuredIntent && (
                <div className="mt-2 ml-9 flex flex-wrap gap-1.5 max-w-[90%]">
                  <span className={`${BDG} border-emerald-500/30 bg-emerald-950/40 font-mono text-emerald-400`}>
                    {msg.structuredIntent.intent_type}
                  </span>
                  {msg.structuredIntent.reference_films && msg.structuredIntent.reference_films.length > 0 && (
                    <span className={`${BDG} border-amber-500/30 bg-amber-950/40 text-amber-300`}>
                      Ref: {msg.structuredIntent.reference_films.join(', ')}
                    </span>
                  )}
                  {msg.structuredIntent.include_genres && msg.structuredIntent.include_genres.length > 0 && (
                    <span className={`${BDG} border-sky-500/30 bg-sky-950/40 text-sky-300`}>
                      +{msg.structuredIntent.include_genres.join(', ')}
                    </span>
                  )}
                  {msg.structuredIntent.exclude_genres && msg.structuredIntent.exclude_genres.length > 0 && (
                    <span className={`${BDG} border-rose-500/30 bg-rose-950/40 text-rose-300`}>
                      -{msg.structuredIntent.exclude_genres.join(', ')}
                    </span>
                  )}
                  {(msg.structuredIntent.year_min || msg.structuredIntent.year_max) && (
                    <span className={`${BDG} border-purple-500/30 bg-purple-950/40 text-purple-300`}>
                      Năm: {msg.structuredIntent.year_min || '…'}–{msg.structuredIntent.year_max || 'nay'}
                    </span>
                  )}
                  {msg.structuredIntent.requested_k && (
                    <span className={`${BDG} border-zinc-700 bg-zinc-900/60 text-zinc-300`}>
                      Top {msg.structuredIntent.requested_k}
                    </span>
                  )}
                </div>
              )}

              {/* Embedded Interactive Movie Cards */}
              {msg.movies && msg.movies.length > 0 && (
                <div className="mt-2.5 ml-9 w-[calc(100%-2.25rem)] space-y-2">
                  {msg.movies.map((movie) => {
                    const inWatchlist = isWatchlisted(movie.id);
                    return (
                      <div
                        key={movie.id}
                        className="group flex gap-3 rounded-xl border border-surface-border/90 bg-gradient-to-r from-surface-elevated/95 to-surface/90 p-2.5 transition-all duration-200 hover:border-brand/40 hover:shadow-card-hover"
                      >
                        {/* Poster */}
                        <div className="relative h-20 w-14 shrink-0 overflow-hidden rounded-lg border border-white/10 bg-zinc-900 shadow-sm">
                          <Image
                            src={movie.poster}
                            alt={movie.title}
                            fill
                            className="object-cover transition-transform duration-300 group-hover:scale-105"
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
                                className="truncate text-xs sm:text-sm font-bold text-white hover:text-brand transition-colors"
                              >
                                {movie.title}
                              </Link>
                              <span className="flex items-center gap-0.5 text-[11px] font-black text-amber-400 shrink-0">
                                <Star size={11} className="fill-amber-400 drop-shadow-[0_0_3px_rgba(251,191,36,0.6)]" />{' '}
                                {movie.rating}
                              </span>
                            </div>
                            <p className="text-[11px] text-zinc-400 mt-0.5 truncate">
                              {movie.year} • {movie.runtime} • {movie.genres.join(', ')}
                            </p>
                          </div>

                          {/* Quick Actions */}
                          <div className="mt-2 flex items-center gap-2">
                            <Link
                              href={`/movies/${movie.id}`}
                              onClick={onClose}
                              className="inline-flex items-center gap-1 rounded-md bg-brand px-2.5 py-1 text-[10px] font-bold text-zinc-950 hover:bg-brand-hover shadow-brand-sm transition-transform active:scale-95 cursor-pointer"
                            >
                              <Play size={10} className="fill-current" /> Xem chi tiết
                            </Link>

                            <button
                              onClick={() => toggleWatchlist(movie.id, movie.title)}
                              className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-[10px] font-medium transition-all active:scale-95 cursor-pointer ${
                                inWatchlist
                                  ? 'border-brand/50 bg-brand/15 text-brand font-semibold'
                                  : 'border-white/10 bg-surface text-zinc-300 hover:border-brand/40 hover:text-white'
                              }`}
                            >
                              {inWatchlist ? (
                                <>
                                  <Check size={10} className="text-brand stroke-[2.5]" /> Đã lưu
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

              {/* Follow-up Suggestions (Sleek tags with subtle glow) */}
              {msg.followUps && msg.followUps.length > 0 && (
                <div className="mt-2 ml-9 flex flex-wrap gap-1.5">
                  {msg.followUps.map((prompt) => (
                    <button
                      key={prompt}
                      disabled={isTyping}
                      onClick={() => handleSend(prompt)}
                      className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-surface-elevated/90 px-3 py-1 text-[11px] font-medium text-zinc-300 transition-all hover:border-brand/50 hover:text-white hover:bg-brand/10 hover:shadow-brand-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed active:scale-95"
                    >
                      <Sparkles size={10} className="text-brand" />
                      <span>{prompt}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* Typing indicator */}
          {isTyping && (
            <div className="flex items-center gap-2 text-xs text-zinc-200 bg-surface-elevated/90 border border-brand/40 rounded-2xl px-4 py-2 w-fit shadow-brand-sm backdrop-blur-md">
              <span className="flex gap-1">
                <span
                  className="h-1.5 w-1.5 rounded-full bg-brand animate-bounce"
                  style={{ animationDelay: '0ms' }}
                />
                <span
                  className="h-1.5 w-1.5 rounded-full bg-brand animate-bounce"
                  style={{ animationDelay: '150ms' }}
                />
                <span
                  className="h-1.5 w-1.5 rounded-full bg-brand animate-bounce"
                  style={{ animationDelay: '300ms' }}
                />
              </span>
              <span className="font-medium text-zinc-300">CineBot đang suy luận...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="border-t border-surface-border/80 bg-surface-elevated/90 p-3.5 backdrop-blur-md">
          <div className="flex items-center gap-2 rounded-xl border border-surface-border bg-surface px-3.5 py-2.5 transition-all focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/20 shadow-inner">
            <input
              ref={inputRef}
              type="text"
              value={input}
              disabled={isTyping}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isTyping ? 'CineBot đang phản hồi...' : 'Hỏi CineBot về phim hoạt hình...'}
              className="w-full bg-transparent text-xs sm:text-sm text-white placeholder:text-zinc-500 focus:outline-none disabled:opacity-60"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isTyping}
              className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand text-zinc-950 transition-all hover:bg-brand-hover hover:scale-105 active:scale-95 shadow-brand-sm disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              aria-label="Gửi tin nhắn"
            >
              <Send size={14} className="ml-0.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Floating Trigger Button for CineBot (Clean modern design, accessible 44px touch target)
 */
export function CineBotFloatingTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label="Mở Chatbot CineBot"
      className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-40 flex min-h-[44px] min-w-[44px] items-center gap-2.5 rounded-full border border-surface-border/90 bg-gradient-to-r from-surface-elevated via-surface to-surface-elevated px-4 py-2.5 text-xs font-bold text-white shadow-[0_10px_30px_rgba(0,0,0,0.8),0_0_20px_rgba(16,185,129,0.3)] transition-all duration-200 hover:border-brand hover:scale-105 hover:shadow-[0_12px_35px_rgba(0,0,0,0.9),0_0_25px_rgba(16,185,129,0.5)] active:scale-95 cursor-pointer"
    >
      <div className="relative flex h-2.5 w-2.5 items-center justify-center">
        <span className="absolute h-full w-full rounded-full bg-brand animate-ping opacity-75" />
        <span className="relative h-2 w-2 rounded-full bg-brand shadow-brand-sm" />
      </div>
      <span>Hỏi CineBot</span>
    </button>
  );
}
