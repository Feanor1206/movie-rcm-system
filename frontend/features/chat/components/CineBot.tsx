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
  'Gợi ý phim Sci-Fi vũ trụ kỳ vĩ',
  'Tìm phim trinh thám đấu trí nghẹt thở',
  'Top phim đánh giá cao nhất',
  'Phim tình cảm nhẹ nhàng chữa lành',
  'Phim mới phát hành năm 2026',
];

export function CineBot({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { isWatchlisted, toggleWatchlist } = useWatchlist();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'bot',
      text: 'Xin chào! Tôi là CineBot. Bạn đang tìm phim theo thể loại, tâm trạng hay muốn gợi ý gì cho buổi xem phim tối nay?',
      timestamp: 'Vừa xong',
      followUps: QUICK_PROMPTS.slice(0, 3),
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

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
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      console.error('Lỗi nhận phản hồi:', err);
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
        text: 'Cuộc trò chuyện đã được làm mới. Bạn cần tôi tìm phim gì tiếp theo?',
        timestamp: 'Vừa xong',
        followUps: QUICK_PROMPTS.slice(0, 3),
      },
    ]);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-end p-0 sm:p-6 bg-black/60 backdrop-blur-sm animate-fade-in pointer-events-auto">
      <div className="flex h-full w-full flex-col overflow-hidden bg-zinc-950 border-0 sm:border sm:border-zinc-800 sm:rounded-xl sm:h-[620px] sm:w-[440px] sm:shadow-2xl">
        {/* Chatbot Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900 px-4 py-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-white">CineBot</h2>
              <span className="text-[11px] text-emerald-400 font-medium">• Sẵn sàng</span>
            </div>
            <p className="text-[11px] text-zinc-400">Trợ lý gợi ý phim điện ảnh</p>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={resetChat}
              title="Làm mới"
              className="rounded p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white cursor-pointer"
            >
              <RotateCcw size={15} />
            </button>
            <button
              onClick={onClose}
              title="Đóng"
              className="rounded p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white cursor-pointer"
            >
              <X size={18} />
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
                    ? 'bg-cinema-red text-white'
                    : 'bg-zinc-900 text-zinc-100 border border-zinc-800'
                }`}
              >
                <p>{msg.text}</p>
                <span
                  className={`mt-1 block text-[10px] ${
                    msg.sender === 'user' ? 'text-white/70 text-right' : 'text-zinc-500'
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
                    return (
                      <div
                        key={movie.id}
                        className="flex gap-3 rounded-lg border border-zinc-800 bg-zinc-900 p-2.5 transition-colors hover:border-zinc-700"
                      >
                        {/* Poster */}
                        <div className="relative h-20 w-14 shrink-0 overflow-hidden rounded border border-zinc-800 bg-zinc-950">
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
                                className="truncate text-xs sm:text-sm font-semibold text-white hover:text-cinema-red transition-colors"
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
                              className="inline-flex items-center gap-1 rounded bg-cinema-red px-2 py-0.5 text-[10px] font-semibold text-white hover:bg-cinema-red-hover cursor-pointer"
                            >
                              <Play size={10} className="fill-current" /> Xem chi tiết
                            </Link>

                            <button
                              onClick={() => toggleWatchlist(movie.id, movie.title)}
                              className="inline-flex items-center gap-1 rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5 text-[10px] font-medium text-zinc-200 hover:border-zinc-500 hover:text-white cursor-pointer"
                            >
                              {inWatchlist ? (
                                <>
                                  <Check size={10} className="text-cinema-red" /> Đã lưu
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
                      onClick={() => handleSend(prompt)}
                      className="rounded border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-[11px] text-zinc-300 transition-colors hover:border-zinc-600 hover:text-white cursor-pointer"
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
            <div className="flex items-center gap-2 text-xs text-zinc-400 bg-zinc-900 border border-zinc-800 rounded-md px-3 py-1.5 w-fit">
              <span className="flex gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-cinema-red animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="h-1.5 w-1.5 rounded-full bg-cinema-red animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="h-1.5 w-1.5 rounded-full bg-cinema-red animate-bounce" style={{ animationDelay: '300ms' }} />
              </span>
              <span>CineBot đang tìm kiếm...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="border-t border-zinc-800 bg-zinc-900 p-3">
          <div className="flex items-center gap-2 rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 focus-within:border-cinema-red">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Nhập câu hỏi hoặc yêu cầu gợi ý..."
              className="w-full bg-transparent text-xs sm:text-sm text-white placeholder:text-zinc-500 focus:outline-none"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim()}
              className="grid h-7 w-7 place-items-center rounded bg-cinema-red text-white transition hover:bg-cinema-red-hover disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
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
 * Floating Trigger Button for CineBot (Clean rectangular design, no oversized pills or ping dots)
 */
export function CineBotFloatingTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label="Mở Chatbot CineBot"
      className="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-md border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-xs font-semibold text-white shadow-lg transition hover:border-cinema-red hover:bg-zinc-850 cursor-pointer"
    >
      <span className="h-2 w-2 rounded-full bg-cinema-red" />
      <span>Hỏi CineBot</span>
    </button>
  );
}
