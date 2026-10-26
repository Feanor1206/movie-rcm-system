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
  Film,
} from 'lucide-react';
import { sendChatMessage, ChatMessage } from '@/lib/services/chatService';
import { useWatchlist } from '@/lib/context/WatchlistContext';
import { buildMediaItemHref } from '@/lib/services/mediaRouting';
import type { Movie } from '@/types/movie';

const QUICK_PROMPTS = [
  'Jadoo Mùa 1 Tập 1',
  'Jadoo sợ tăng cân',
  'Tìm tiểu phẩm Jadoo',
];

const BTN_HEAD = 'flex h-11 w-11 min-h-[44px] min-w-[44px] items-center justify-center rounded-md text-muted hover:bg-surface-elevated hover:text-ink cursor-pointer';

export function CineBot({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { isWatchlisted, toggleWatchlist } = useWatchlist();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'bot',
      text: 'Chào bạn! Mình là CineBot. Bạn đang muốn xem câu chuyện nào? Kể mình nghe một cái tên hay tình tiết bạn còn nhớ nhé.',
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
      <div className="flex h-full w-full flex-col overflow-hidden bg-surface border-0 sm:border-2 sm:border-surface-border sm:rounded-none sm:h-[620px] sm:w-[440px] sm:shadow-2xl">
        {/* Chatbot Header */}
        <div className="flex items-center justify-between border-b border-surface-border bg-surface-muted px-4 py-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 id="cinebot-dialog-title" className="comic-heading text-xl font-bold text-ink">
                CineBot
              </h2>
              <span className="rounded bg-brand/15 border border-brand/30 px-1.5 py-0.5 text-[10px] text-brand-dark font-semibold">
                Bạn đồng hành
              </span>
            </div>
            <p className="text-[11px] text-muted">Gợi ý phim hoạt hình</p>
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
                className={`max-w-[90%] rounded-[16px_16px_16px_2px] px-3.5 py-2.5 text-xs sm:text-sm leading-relaxed ${
                  msg.sender === 'user'
                    ? 'bg-mint text-ink border border-ink font-medium shadow-brand-sm !rounded-[16px_16px_2px_16px]'
                    : 'bg-surface-muted text-ink border border-surface-border'
                }`}
              >
                <p>{msg.text.split(/(\*\*[^*]+\*\*)/g).map((part, i) => part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part)}</p>
                <span
                  className={`mt-1 block text-[10px] ${
                    msg.sender === 'user' ? 'text-zinc-950/70 text-right font-medium' : 'text-muted'
                  }`}
                >
                  {msg.timestamp}
                </span>
              </div>

              {/* Embedded Interactive Movie Cards */}
              {msg.movies && msg.movies.length > 0 && (
                <div className="mt-2.5 w-full space-y-2">
                  {msg.movies.map((movie) => {
                    const inWatchlist = isWatchlisted(movie.id);
                    const mediaHref = buildMediaItemHref(movie);
                    const hasPoster = Boolean(movie.poster && movie.poster.trim());
                    return (
                      <div
                        key={movie.id}
                        className="flex gap-3 rounded-lg border border-surface-border bg-surface-muted p-2.5 transition-colors hover:border-ink/30"
                      >
                        {/* Poster */}
                        <div className="relative h-20 w-14 shrink-0 overflow-hidden rounded border border-surface-border bg-surface">
                          {hasPoster ? (
                            <Image
                              src={movie.poster}
                              alt={movie.title}
                              fill
                              className="object-cover"
                              sizes="56px"
                            />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center bg-mint text-muted">
                              <Film size={20} />
                            </div>
                          )}
                        </div>

                        {/* Details */}
                        <div className="flex flex-col justify-between flex-1 min-w-0">
                          <div>
                            <div className="flex items-center justify-between gap-1">
                              <Link
                                href={mediaHref}
                                onClick={onClose}
                                className="truncate text-xs sm:text-sm font-semibold text-ink hover:text-brand transition-colors"
                              >
                                {movie.title}
                              </Link>
                              <span className="flex items-center gap-0.5 text-[11px] font-bold text-amber-400 shrink-0">
                                <Star size={11} className="fill-amber-400" /> {movie.rating}
                              </span>
                            </div>
                            <p className="text-[11px] text-muted mt-0.5">
                              {movie.year} · {movie.runtime} · {movie.genres.join(', ')}
                            </p>
                          </div>

                          {/* Quick Actions */}
                          <div className="mt-2 flex items-center gap-2">
                            <Link
                              href={mediaHref}
                              onClick={onClose}
                              className="inline-flex items-center gap-1 rounded bg-brand px-2 py-0.5 text-[10px] font-bold text-zinc-950 hover:bg-brand-hover shadow-brand-sm cursor-pointer"
                            >
                              <Play size={10} className="fill-current" /> Xem chi tiết
                            </Link>

                            <button
                              onClick={() => toggleWatchlist(movie.id, movie.title)}
                              className="inline-flex items-center gap-1 rounded border border-ink/30 bg-surface-elevated px-2 py-0.5 text-[10px] font-medium text-ink hover:border-zinc-500 hover:text-ink cursor-pointer"
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
                      className="rounded border border-ink/30 bg-mint px-2.5 py-1 text-[11px] text-muted transition-colors hover:border-ink hover:text-ink cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
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
            <div className="flex items-center gap-2 text-xs text-muted bg-surface-muted border border-brand/40 rounded-md px-3 py-1.5 w-fit">
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
              className="w-full bg-transparent text-xs sm:text-sm text-ink placeholder:text-muted focus:outline-none disabled:opacity-60"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isTyping}
              className="grid h-11 w-11 shrink-0 place-items-center border border-ink bg-brand text-ink transition hover:bg-brand-hover shadow-brand-sm disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
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

export { CineBotFloatingTrigger } from './CineBotFloatingTrigger';
