'use client';

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useRef,
  useCallback,
  ReactNode,
} from 'react';
import { CineBot, CineBotFloatingTrigger } from '@/features/chat/components/CineBot';
import { AuthModal } from '@/features/auth/components/AuthModal';
import { useAuth } from './AuthContext';

export type Toast = {
  id: string;
  message: string;
  type?: 'success' | 'info' | 'error';
};

type WatchlistContextType = {
  watchlist: string[];
  favorites: string[];
  ratings: Record<string, number>;
  toggleWatchlist: (id: string, title?: string, poster?: string) => Promise<boolean>;
  toggleFavorite: (id: string, title?: string, poster?: string) => Promise<boolean>;
  rateMovie: (id: string, rating: number, title?: string) => Promise<boolean>;
  removeRating: (id: string, title?: string) => Promise<boolean>;
  isWatchlisted: (id: string) => boolean;
  isFavorite: (id: string) => boolean;
  getRating: (id: string) => number | undefined;
  isActionPending: (id: string, action?: 'watchlist' | 'favorite' | 'rating') => boolean;
  isActionUnconfirmed: (id: string, action?: 'watchlist' | 'favorite' | 'rating') => boolean;
  getActionIntent: (id: string, action?: 'watchlist' | 'favorite' | 'rating') => 'add' | 'remove' | 'rate' | 'remove_rating' | null;
  getUnconfirmedRating: (id: string) => number | undefined;
  isLibraryLoading: boolean;
  libraryError: string | null;
  refetchLibrary: () => Promise<void>;
  isGuestMode: boolean;
  toasts: Toast[];
  showToast: (message: string, type?: 'success' | 'info' | 'error') => void;
  dismissToast: (id: string) => void;
  isChatOpen: boolean;
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
};

const WatchlistContext = createContext<WatchlistContextType | undefined>(undefined);

const SPRINGBOOT_API = process.env.NEXT_PUBLIC_SPRINGBOOT_API_URL || 'http://localhost:8080/api';
const GUEST_STORAGE_KEY = 'dippie_guest_library_v1';
const REQUEST_TIMEOUT_MS = 7000;

type GuestStorageData = {
  watchlist: string[];
  favorites: string[];
  ratings: Record<string, number>;
};

type LibrarySnapshot = {
  ownerKey: string;
  watchlist: string[];
  favorites: string[];
  ratings: Record<string, number>;
};

type OperationRecord = {
  id: number;
  action: 'watchlist' | 'favorite' | 'rating';
  movieId: string;
  readVersionAtStart: number;
  committedAtReadVersion: number | null;
  status: 'pending' | 'committed' | 'uncertain';
  desiredValue: any;
};

function readGuestStorage(): GuestStorageData {
  if (typeof window === 'undefined') {
    return { watchlist: [], favorites: [], ratings: {} };
  }
  try {
    const raw = localStorage.getItem(GUEST_STORAGE_KEY);
    if (!raw) return { watchlist: [], favorites: [], ratings: {} };
    const parsed = JSON.parse(raw);
    const validWatchlist = Array.isArray(parsed.watchlist)
      ? parsed.watchlist.filter((id: unknown) => typeof id === 'string' && id.trim().length > 0)
      : [];
    const validFavorites = Array.isArray(parsed.favorites)
      ? parsed.favorites.filter((id: unknown) => typeof id === 'string' && id.trim().length > 0)
      : [];
    const validRatings: Record<string, number> = {};
    if (typeof parsed.ratings === 'object' && parsed.ratings !== null && !Array.isArray(parsed.ratings)) {
      Object.entries(parsed.ratings).forEach(([k, v]) => {
        if (
          typeof k === 'string' &&
          k.trim().length > 0 &&
          typeof v === 'number' &&
          Number.isFinite(v) &&
          v >= 1 &&
          v <= 10
        ) {
          validRatings[k] = Math.round(v);
        }
      });
    }
    return {
      watchlist: validWatchlist,
      favorites: validFavorites,
      ratings: validRatings,
    };
  } catch {
    return { watchlist: [], favorites: [], ratings: {} };
  }
}

function writeGuestStorage(data: GuestStorageData): boolean {
  if (typeof window === 'undefined') return false;
  try {
    localStorage.setItem(GUEST_STORAGE_KEY, JSON.stringify(data));
    return true;
  } catch {
    return false;
  }
}

function getActorKey(status: string, user: { id: number } | null, token: string | null): string {
  if (status === 'authenticated' && user && token) {
    return `user:${user.id}:${token}`;
  }
  if (status === 'guest') {
    return 'guest';
  }
  return `status:${status}`;
}

export function WatchlistProvider({ children }: { children: ReactNode }) {
  const { user, token, status, isAuthenticated, handleSessionExpired } = useAuth();

  const currentActorKey = getActorKey(status, user, token);

  // Snapshot tied explicitly to its owner (F2 / G1)
  const [snapshot, setSnapshot] = useState<LibrarySnapshot>(() => {
    if (typeof window !== 'undefined' && status === 'guest') {
      const g = readGuestStorage();
      return {
        ownerKey: 'guest',
        watchlist: g.watchlist,
        favorites: g.favorites,
        ratings: g.ratings,
      };
    }
    return {
      ownerKey: currentActorKey,
      watchlist: [],
      favorites: [],
      ratings: {},
    };
  });

  const [isLibraryLoading, setIsLibraryLoading] = useState<boolean>(true);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [, setPendingUpdateTick] = useState<number>(0);

  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isChatOpen, setIsChatOpen] = useState(false);

  // G1/G2/G3/H1/H2: Session epoch, read versioning, operation ID, and mutation journal
  const sessionGenRef = useRef<number>(0);
  const readGenRef = useRef<number>(0);
  const lastKnownActorKeyRef = useRef<string>(currentActorKey);
  const operationCounterRef = useRef<number>(0);

  // Structured mutation journal and locks
  const operationsJournalRef = useRef<Map<string, OperationRecord>>(new Map());
  const syncPendingLocksRef = useRef<Set<string>>(new Set());
  const activeMutationAbortControllersRef = useRef<Map<number, AbortController>>(new Map());
  const activeReadAbortControllerRef = useRef<AbortController | null>(null);

  // Detect actor / session change synchronously during render and bump session lifecycle
  if (lastKnownActorKeyRef.current !== currentActorKey) {
    sessionGenRef.current += 1;
    lastKnownActorKeyRef.current = currentActorKey;

    // Reset journal, active locks, and read version for new actor session
    operationsJournalRef.current.clear();
    syncPendingLocksRef.current.clear();
    readGenRef.current = 0;

    // Abort in-flight mutations from previous session
    for (const ctrl of activeMutationAbortControllersRef.current.values()) {
      try {
        ctrl.abort();
      } catch {}
    }
    activeMutationAbortControllersRef.current.clear();

    // Abort in-flight read from previous session
    if (activeReadAbortControllerRef.current) {
      try {
        activeReadAbortControllerRef.current.abort();
      } catch {}
      activeReadAbortControllerRef.current = null;
    }
  }

  // F2: Derive visible values strictly matching currentActorKey
  const isOwnerCurrent = snapshot.ownerKey === currentActorKey;
  const visibleWatchlist: string[] = isOwnerCurrent
    ? snapshot.watchlist
    : status === 'guest' && typeof window !== 'undefined'
    ? readGuestStorage().watchlist
    : [];

  const visibleFavorites: string[] = isOwnerCurrent
    ? snapshot.favorites
    : status === 'guest' && typeof window !== 'undefined'
    ? readGuestStorage().favorites
    : [];

  const visibleRatings: Record<string, number> = isOwnerCurrent
    ? snapshot.ratings
    : status === 'guest' && typeof window !== 'undefined'
    ? readGuestStorage().ratings
    : {};

  const showToast = useCallback((message: string, type: 'success' | 'info' | 'error' = 'success') => {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
    setToasts((prev) => [...prev.slice(-3), { id, message, type }]);
    setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id));
    }, 3200);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // G1/G2/G3/H1/H2: Unified authoritative library fetch and reconciliation core
  const performFetchLibrary = useCallback(
    async (options?: { isBackgroundReconcile?: boolean }) => {
      const thisActorKey = currentActorKey;
      const thisSessionGen = sessionGenRef.current;
      readGenRef.current += 1;
      const thisReadVersion = readGenRef.current;

      // 1. Unverified or intermediate states
      if (!isAuthenticated || !token || !user) {
        if (status === 'checking') {
          setIsLibraryLoading(true);
          return;
        }
        if (status === 'unavailable') {
          setIsLibraryLoading(false);
          setLibraryError('Dịch vụ xác thực tạm thời không khả dụng.');
          setSnapshot({
            ownerKey: thisActorKey,
            watchlist: [],
            favorites: [],
            ratings: {},
          });
          return;
        }
        // status === 'guest'
        const guestData = readGuestStorage();
        if (sessionGenRef.current === thisSessionGen && lastKnownActorKeyRef.current === thisActorKey) {
          setSnapshot({
            ownerKey: 'guest',
            watchlist: guestData.watchlist,
            favorites: guestData.favorites,
            ratings: guestData.ratings,
          });
          setIsLibraryLoading(false);
          setLibraryError(null);
        }
        return;
      }

      // 2. Authenticated mode: fetch authoritative data
      if (!options?.isBackgroundReconcile) {
        setIsLibraryLoading(true);
      }

      if (activeReadAbortControllerRef.current) {
        try {
          activeReadAbortControllerRef.current.abort();
        } catch {}
        activeReadAbortControllerRef.current = null;
      }

      const abortCtrl = new AbortController();
      activeReadAbortControllerRef.current = abortCtrl;

      let timeoutId: NodeJS.Timeout | null = setTimeout(() => {
        abortCtrl.abort();
      }, REQUEST_TIMEOUT_MS);

      try {
        const headers = {
          Authorization: `Bearer ${token}`,
          Accept: 'application/json',
        };

        const [resWatchlist, resFavorites, resRatings] = await Promise.all([
          fetch(`${SPRINGBOOT_API}/users/watchlist`, { headers, signal: abortCtrl.signal }),
          fetch(`${SPRINGBOOT_API}/users/favorites`, { headers, signal: abortCtrl.signal }),
          fetch(`${SPRINGBOOT_API}/users/ratings`, { headers, signal: abortCtrl.signal }),
        ]);

        // F1: Guard 401 callback against stale session
        if (resWatchlist.status === 401 || resFavorites.status === 401 || resRatings.status === 401) {
          if (sessionGenRef.current === thisSessionGen && lastKnownActorKeyRef.current === thisActorKey) {
            handleSessionExpired();
            setLibraryError('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
          }
          setIsLibraryLoading(false);
          return;
        }

        if (!resWatchlist.ok || !resFavorites.ok || !resRatings.ok) {
          setLibraryError('Không thể tải toàn bộ thư viện cá nhân từ máy chủ.');
          setIsLibraryLoading(false);
          return;
        }

        const [jsonWatchlist, jsonFavorites, jsonRatings] = await Promise.all([
          resWatchlist.json(),
          resFavorites.json(),
          resRatings.json(),
        ]);

        if (timeoutId) {
          clearTimeout(timeoutId);
          timeoutId = null;
        }

        // Validate session guard
        if (sessionGenRef.current !== thisSessionGen || lastKnownActorKeyRef.current !== thisActorKey) {
          return;
        }

        const isWatchlistValid = jsonWatchlist?.success === true && Array.isArray(jsonWatchlist?.data);
        const isFavoritesValid = jsonFavorites?.success === true && Array.isArray(jsonFavorites?.data);
        const isRatingsValid = jsonRatings?.success === true && Array.isArray(jsonRatings?.data);

        if (!isWatchlistValid || !isFavoritesValid || !isRatingsValid) {
          setLibraryError('Dữ liệu phản hồi từ máy chủ không hợp lệ.');
          setIsLibraryLoading(false);
          return;
        }

        const nextWatchlist: string[] = jsonWatchlist.data.map((item: any) => item.movieId).filter(Boolean);
        const nextFavorites: string[] = jsonFavorites.data.map((item: any) => item.movieId).filter(Boolean);
        const nextRatings: Record<string, number> = {};
        jsonRatings.data.forEach((r: any) => {
          if (r.movieId && typeof r.rating === 'number') {
            nextRatings[r.movieId] = r.rating;
          }
        });

        // G1, G2, H1 & H2 Reconciliation:
        setSnapshot((prev) => {
          if (sessionGenRef.current !== thisSessionGen || lastKnownActorKeyRef.current !== thisActorKey) {
            return prev;
          }

          const resolvedWatchlist = new Set<string>();
          const resolvedFavorites = new Set<string>();
          const resolvedRatings: Record<string, number> = { ...nextRatings };

          // 1. Process server watchlist
          for (const id of nextWatchlist) {
            const op = operationsJournalRef.current.get(`watchlist:${id}`);
            if (!op) {
              resolvedWatchlist.add(id);
            } else {
              // H1: Read R acknowledges commit ONLY IF R > committedAtReadVersion!
              const isAcknowledged =
                op.status === 'committed' &&
                op.committedAtReadVersion !== null &&
                thisReadVersion > op.committedAtReadVersion;

              if (isAcknowledged) {
                resolvedWatchlist.add(id);
              } else if (op.status === 'uncertain') {
                if (op.desiredValue === true) {
                  // Background reconcile confirmed item exists on server!
                  op.status = 'committed';
                  op.committedAtReadVersion = thisReadVersion;
                  resolvedWatchlist.add(id);
                } else {
                  if (thisReadVersion > op.readVersionAtStart) {
                    operationsJournalRef.current.delete(`watchlist:${id}`);
                    resolvedWatchlist.add(id);
                  }
                }
              } else {
                if (op.desiredValue === true) resolvedWatchlist.add(id);
              }
            }
          }
          // Process operations that were not in server watchlist
          for (const [key, op] of operationsJournalRef.current.entries()) {
            if (op.action === 'watchlist') {
              const isAcknowledged =
                op.status === 'committed' &&
                op.committedAtReadVersion !== null &&
                thisReadVersion > op.committedAtReadVersion;

              if (!isAcknowledged) {
                if (op.status === 'uncertain') {
                  if (thisReadVersion > op.readVersionAtStart) {
                    operationsJournalRef.current.delete(key);
                  } else {
                    if (op.desiredValue === true) resolvedWatchlist.add(op.movieId);
                    else if (op.desiredValue === false) resolvedWatchlist.delete(op.movieId);
                  }
                } else if (op.desiredValue === true) {
                  resolvedWatchlist.add(op.movieId);
                } else if (op.desiredValue === false) {
                  resolvedWatchlist.delete(op.movieId);
                }
              }
            }
          }

          // 2. Process server favorites
          for (const id of nextFavorites) {
            const op = operationsJournalRef.current.get(`favorite:${id}`);
            if (!op) {
              resolvedFavorites.add(id);
            } else {
              const isAcknowledged =
                op.status === 'committed' &&
                op.committedAtReadVersion !== null &&
                thisReadVersion > op.committedAtReadVersion;

              if (isAcknowledged) {
                resolvedFavorites.add(id);
              } else if (op.status === 'uncertain') {
                if (op.desiredValue === true) {
                  op.status = 'committed';
                  op.committedAtReadVersion = thisReadVersion;
                  resolvedFavorites.add(id);
                } else {
                  if (thisReadVersion > op.readVersionAtStart) {
                    operationsJournalRef.current.delete(`favorite:${id}`);
                    resolvedFavorites.add(id);
                  }
                }
              } else {
                if (op.desiredValue === true) resolvedFavorites.add(id);
              }
            }
          }
          for (const [key, op] of operationsJournalRef.current.entries()) {
            if (op.action === 'favorite') {
              const isAcknowledged =
                op.status === 'committed' &&
                op.committedAtReadVersion !== null &&
                thisReadVersion > op.committedAtReadVersion;

              if (!isAcknowledged) {
                if (op.status === 'uncertain') {
                  if (thisReadVersion > op.readVersionAtStart) {
                    operationsJournalRef.current.delete(key);
                  } else {
                    if (op.desiredValue === true) resolvedFavorites.add(op.movieId);
                    else if (op.desiredValue === false) resolvedFavorites.delete(op.movieId);
                  }
                } else if (op.desiredValue === true) {
                  resolvedFavorites.add(op.movieId);
                } else if (op.desiredValue === false) {
                  resolvedFavorites.delete(op.movieId);
                }
              }
            }
          }

          // 3. Process ratings
          for (const [key, op] of operationsJournalRef.current.entries()) {
            if (op.action === 'rating') {
              const isAcknowledged =
                op.status === 'committed' &&
                op.committedAtReadVersion !== null &&
                thisReadVersion > op.committedAtReadVersion;

              if (!isAcknowledged) {
                if (op.status === 'uncertain') {
                  if (thisReadVersion > op.readVersionAtStart) {
                    operationsJournalRef.current.delete(key);
                  } else {
                    if (typeof op.desiredValue === 'number') {
                      resolvedRatings[op.movieId] = op.desiredValue;
                    } else if (op.desiredValue === undefined) {
                      delete resolvedRatings[op.movieId];
                    }
                  }
                } else if (typeof op.desiredValue === 'number') {
                  resolvedRatings[op.movieId] = op.desiredValue;
                } else if (op.desiredValue === undefined) {
                  delete resolvedRatings[op.movieId];
                }
              }
            }
          }

          // H1: Prune committed operations ONLY when thisReadVersion > op.committedAtReadVersion
          for (const [key, op] of operationsJournalRef.current.entries()) {
            if (
              op.status === 'committed' &&
              op.committedAtReadVersion !== null &&
              thisReadVersion > op.committedAtReadVersion
            ) {
              operationsJournalRef.current.delete(key);
            }
          }

          return {
            ownerKey: thisActorKey,
            watchlist: Array.from(resolvedWatchlist),
            favorites: Array.from(resolvedFavorites),
            ratings: resolvedRatings,
          };
        });

        setIsLibraryLoading(false);
        setLibraryError(null);
      } catch (err: unknown) {
        if (timeoutId) {
          clearTimeout(timeoutId);
          timeoutId = null;
        }
        if (sessionGenRef.current !== thisSessionGen || lastKnownActorKeyRef.current !== thisActorKey) {
          return;
        }
        setIsLibraryLoading(false);
        if (
          (err instanceof DOMException && err.name === 'AbortError') ||
          (err as any)?.name === 'AbortError'
        ) {
          setLibraryError('Thời gian tải thư viện quá hạn (timeout).');
        } else {
          setLibraryError('Không thể tải toàn bộ thư viện cá nhân từ máy chủ.');
        }
      } finally {
        if (timeoutId) {
          clearTimeout(timeoutId);
        }
        if (activeReadAbortControllerRef.current === abortCtrl) {
          activeReadAbortControllerRef.current = null;
        }
      }
    },
    [isAuthenticated, token, user, status, currentActorKey, handleSessionExpired]
  );

  useEffect(() => {
    performFetchLibrary();
    return () => {
      if (activeReadAbortControllerRef.current) {
        try {
          activeReadAbortControllerRef.current.abort();
        } catch {}
      }
      for (const ctrl of activeMutationAbortControllersRef.current.values()) {
        try {
          ctrl.abort();
        } catch {}
      }
      activeMutationAbortControllersRef.current.clear();
    };
  }, [performFetchLibrary]);

  const isActionPending = useCallback(
    (id: string, action?: 'watchlist' | 'favorite' | 'rating') => {
      const prefix = `${sessionGenRef.current}:${currentActorKey}`;
      if (!action) {
        return (
          syncPendingLocksRef.current.has(`${prefix}:watchlist:${id}`) ||
          syncPendingLocksRef.current.has(`${prefix}:favorite:${id}`) ||
          syncPendingLocksRef.current.has(`${prefix}:rating:${id}`)
        );
      }
      return syncPendingLocksRef.current.has(`${prefix}:${action}:${id}`);
    },
    [currentActorKey]
  );

  const isActionUnconfirmed = useCallback(
    (id: string, action?: 'watchlist' | 'favorite' | 'rating') => {
      const act = action || 'watchlist';
      const op = operationsJournalRef.current.get(`${act}:${id}`);
      return op?.status === 'uncertain';
    },
    []
  );

  const getActionIntent = useCallback(
    (id: string, action?: 'watchlist' | 'favorite' | 'rating'): 'add' | 'remove' | 'rate' | 'remove_rating' | null => {
      const act = action || 'watchlist';
      const op = operationsJournalRef.current.get(`${act}:${id}`);
      if (!op || op.status !== 'uncertain') return null;
      if (act === 'watchlist' || act === 'favorite') {
        return op.desiredValue === true ? 'add' : 'remove';
      }
      if (act === 'rating') {
        return typeof op.desiredValue === 'number' ? 'rate' : 'remove_rating';
      }
      return null;
    },
    []
  );

  const getUnconfirmedRating = useCallback(
    (id: string): number | undefined => {
      const op = operationsJournalRef.current.get(`rating:${id}`);
      if (op && op.status === 'uncertain' && typeof op.desiredValue === 'number') {
        return op.desiredValue;
      }
      return undefined;
    },
    []
  );

  // Watchlist Mutation
  const toggleWatchlist = async (
    id: string,
    title?: string,
    poster?: string
  ): Promise<boolean> => {
    const mutationActorKey = currentActorKey;
    const mutationSessionGen = sessionGenRef.current;
    const lockKey = `${mutationSessionGen}:${mutationActorKey}:watchlist:${id}`;
    const opKey = `watchlist:${id}`;

    if (syncPendingLocksRef.current.has(lockKey)) return false;
    syncPendingLocksRef.current.add(lockKey);
    setPendingUpdateTick((t) => t + 1);

    const existingOp = operationsJournalRef.current.get(opKey);
    // H2: If retrying an uncertain outcome, retain original desired intent; do not invert!
    const isAdding =
      existingOp && existingOp.status === 'uncertain'
        ? existingOp.desiredValue
        : !visibleWatchlist.includes(id);

    const alreadyInWatchlist = !isAdding;
    const displayTitle = title || id;

    const isStillCurrentSession = () => {
      return (
        sessionGenRef.current === mutationSessionGen &&
        lastKnownActorKeyRef.current === mutationActorKey
      );
    };

    if (status === 'checking') {
      showToast('Đang kiểm tra phiên đăng nhập, vui lòng đợi...', 'info');
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
      return false;
    }
    if (status === 'unavailable') {
      showToast('Dịch vụ xác thực tạm thời không khả dụng. Vui lòng thử lại sau.', 'error');
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
      return false;
    }

    // 1. Guest Mode
    if (status === 'guest' || !isAuthenticated || !token) {
      const nextWatchlist = alreadyInWatchlist
        ? visibleWatchlist.filter((item) => item !== id)
        : [...visibleWatchlist, id];

      const saved = writeGuestStorage({
        watchlist: nextWatchlist,
        favorites: visibleFavorites,
        ratings: visibleRatings,
      });

      if (!saved) {
        showToast('Không thể lưu vào bộ nhớ thiết bị.', 'error');
        syncPendingLocksRef.current.delete(lockKey);
        setPendingUpdateTick((t) => t + 1);
        return false;
      }

      setSnapshot({
        ownerKey: 'guest',
        watchlist: nextWatchlist,
        favorites: visibleFavorites,
        ratings: visibleRatings,
      });

      if (alreadyInWatchlist) {
        showToast(`Đã xóa ${displayTitle} khỏi Danh sách xem (trên thiết bị)`, 'info');
      } else {
        showToast(`Đã lưu ${displayTitle} vào Danh sách xem (trên thiết bị)`, 'success');
      }
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
      return true;
    }

    // 2. Authenticated Mode
    const opId = ++operationCounterRef.current;
    operationsJournalRef.current.set(opKey, {
      id: opId,
      action: 'watchlist',
      movieId: id,
      readVersionAtStart: readGenRef.current,
      committedAtReadVersion: null,
      status: 'pending',
      desiredValue: isAdding,
    });

    setSnapshot((prev) => {
      const isSameActor = prev.ownerKey === mutationActorKey;
      const baseWatchlist = isSameActor ? prev.watchlist : [];
      const nextW = isAdding
        ? (baseWatchlist.includes(id) ? baseWatchlist : [...baseWatchlist, id])
        : baseWatchlist.filter((item) => item !== id);

      return {
        ownerKey: mutationActorKey,
        watchlist: nextW,
        favorites: isSameActor ? prev.favorites : [],
        ratings: isSameActor ? prev.ratings : {},
      };
    });

    const abortCtrl = new AbortController();
    activeMutationAbortControllersRef.current.set(opId, abortCtrl);

    let timeoutId: NodeJS.Timeout | null = setTimeout(() => {
      abortCtrl.abort();
    }, REQUEST_TIMEOUT_MS);

    try {
      if (alreadyInWatchlist) {
        const res = await fetch(`${SPRINGBOOT_API}/users/watchlist/${encodeURIComponent(id)}`, {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'application/json',
          },
          signal: abortCtrl.signal,
        });

        if (res.status === 401) {
          if (isStillCurrentSession()) {
            handleSessionExpired();
            showToast('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.', 'error');
          }
          throw new Error('Phiên đăng nhập đã hết hạn.');
        }
        if (res.status === 403) {
          throw new Error('Bạn không có quyền thực hiện thao tác này.');
        }
        if (!res.ok) throw new Error(`Xóa khỏi Danh sách xem thất bại (HTTP ${res.status})`);

        const json = await res.json();
        if (timeoutId) {
          clearTimeout(timeoutId);
          timeoutId = null;
        }

        if (!json || json.success !== true) throw new Error('Phản hồi từ máy chủ không hợp lệ.');

        if (isStillCurrentSession()) {
          const op = operationsJournalRef.current.get(opKey);
          if (op && op.id === opId) {
            op.status = 'committed';
            op.committedAtReadVersion = readGenRef.current;
          }
          showToast(`Đã xóa ${displayTitle} khỏi Danh sách xem`, 'info');
          return true;
        }
        return false;
      } else {
        const res = await fetch(`${SPRINGBOOT_API}/users/watchlist`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            Accept: 'application/json',
          },
          body: JSON.stringify({
            movieId: id,
            movieTitle: displayTitle,
            posterUrl: poster || '',
          }),
          signal: abortCtrl.signal,
        });

        if (res.status === 401) {
          if (isStillCurrentSession()) {
            handleSessionExpired();
            showToast('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.', 'error');
          }
          throw new Error('Phiên đăng nhập đã hết hạn.');
        }
        if (res.status === 403) {
          throw new Error('Bạn không có quyền thực hiện thao tác này.');
        }
        if (!res.ok) throw new Error(`Lưu vào Danh sách xem thất bại (HTTP ${res.status})`);

        const json = await res.json();
        if (timeoutId) {
          clearTimeout(timeoutId);
          timeoutId = null;
        }

        if (!json || json.success !== true) throw new Error('Phản hồi từ máy chủ không hợp lệ.');

        if (isStillCurrentSession()) {
          const op = operationsJournalRef.current.get(opKey);
          if (op && op.id === opId) {
            op.status = 'committed';
            op.committedAtReadVersion = readGenRef.current;
          }
          showToast(`Đã lưu ${displayTitle} vào Danh sách xem`, 'success');
          return true;
        }
        return false;
      }
    } catch (err: unknown) {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      if (isStillCurrentSession()) {
        const isTimeout =
          (err instanceof DOMException && err.name === 'AbortError') ||
          (err as any)?.name === 'AbortError';
        const isNetworkError =
          err instanceof TypeError || (err as any)?.name === 'TypeError';

        if (isTimeout || isNetworkError) {
          // H2: Unknown write outcome - mark as uncertain to retain intent and avoid inversion on retry
          const op = operationsJournalRef.current.get(opKey);
          if (op && op.id === opId) {
            op.status = 'uncertain';
          }
          showToast('Thời gian gửi yêu cầu quá hạn hoặc mất kết nối. Đang kiểm tra lại trạng thái...', 'error');
          performFetchLibrary({ isBackgroundReconcile: true });
        } else {
          // Definite failure: delete op and rollback
          const op = operationsJournalRef.current.get(opKey);
          if (op && op.id === opId) {
            operationsJournalRef.current.delete(opKey);
          }
          setSnapshot((prev) => {
            if (prev.ownerKey !== mutationActorKey) return prev;
            return {
              ...prev,
              watchlist: alreadyInWatchlist
                ? (prev.watchlist.includes(id) ? prev.watchlist : [...prev.watchlist, id])
                : prev.watchlist.filter((item) => item !== id),
            };
          });
          showToast('Không thể cập nhật Danh sách xem. Vui lòng thử lại.', 'error');
        }
      }
      return false;
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      activeMutationAbortControllersRef.current.delete(opId);
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
    }
  };

  // Favorites Mutation
  const toggleFavorite = async (
    id: string,
    title?: string,
    poster?: string
  ): Promise<boolean> => {
    const mutationActorKey = currentActorKey;
    const mutationSessionGen = sessionGenRef.current;
    const lockKey = `${mutationSessionGen}:${mutationActorKey}:favorite:${id}`;
    const opKey = `favorite:${id}`;

    if (syncPendingLocksRef.current.has(lockKey)) return false;
    syncPendingLocksRef.current.add(lockKey);
    setPendingUpdateTick((t) => t + 1);

    const existingOp = operationsJournalRef.current.get(opKey);
    const isAdding =
      existingOp && existingOp.status === 'uncertain'
        ? existingOp.desiredValue
        : !visibleFavorites.includes(id);

    const alreadyInFavorites = !isAdding;
    const displayTitle = title || id;

    const isStillCurrentSession = () => {
      return (
        sessionGenRef.current === mutationSessionGen &&
        lastKnownActorKeyRef.current === mutationActorKey
      );
    };

    if (status === 'checking') {
      showToast('Đang kiểm tra phiên đăng nhập, vui lòng đợi...', 'info');
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
      return false;
    }
    if (status === 'unavailable') {
      showToast('Dịch vụ xác thực tạm thời không khả dụng. Vui lòng thử lại sau.', 'error');
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
      return false;
    }

    // 1. Guest Mode
    if (status === 'guest' || !isAuthenticated || !token) {
      const nextFavorites = alreadyInFavorites
        ? visibleFavorites.filter((item) => item !== id)
        : [...visibleFavorites, id];

      const saved = writeGuestStorage({
        watchlist: visibleWatchlist,
        favorites: nextFavorites,
        ratings: visibleRatings,
      });

      if (!saved) {
        showToast('Không thể lưu vào bộ nhớ thiết bị.', 'error');
        syncPendingLocksRef.current.delete(lockKey);
        setPendingUpdateTick((t) => t + 1);
        return false;
      }

      setSnapshot({
        ownerKey: 'guest',
        watchlist: visibleWatchlist,
        favorites: nextFavorites,
        ratings: visibleRatings,
      });

      if (alreadyInFavorites) {
        showToast(`Đã xóa ${displayTitle} khỏi Yêu thích (trên thiết bị)`, 'info');
      } else {
        showToast(`Đã thêm ${displayTitle} vào Yêu thích (trên thiết bị)`, 'success');
      }
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
      return true;
    }

    // 2. Authenticated Mode
    const opId = ++operationCounterRef.current;
    operationsJournalRef.current.set(opKey, {
      id: opId,
      action: 'favorite',
      movieId: id,
      readVersionAtStart: readGenRef.current,
      committedAtReadVersion: null,
      status: 'pending',
      desiredValue: isAdding,
    });

    setSnapshot((prev) => {
      const isSameActor = prev.ownerKey === mutationActorKey;
      const baseFavorites = isSameActor ? prev.favorites : [];
      const nextF = alreadyInFavorites
        ? baseFavorites.filter((item) => item !== id)
        : baseFavorites.includes(id)
        ? baseFavorites
        : [...baseFavorites, id];

      return {
        ownerKey: mutationActorKey,
        watchlist: isSameActor ? prev.watchlist : [],
        favorites: nextF,
        ratings: isSameActor ? prev.ratings : {},
      };
    });

    const abortCtrl = new AbortController();
    activeMutationAbortControllersRef.current.set(opId, abortCtrl);

    let timeoutId: NodeJS.Timeout | null = setTimeout(() => {
      abortCtrl.abort();
    }, REQUEST_TIMEOUT_MS);

    try {
      if (alreadyInFavorites) {
        const res = await fetch(`${SPRINGBOOT_API}/users/favorites/${encodeURIComponent(id)}`, {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'application/json',
          },
          signal: abortCtrl.signal,
        });

        if (res.status === 401) {
          if (isStillCurrentSession()) {
            handleSessionExpired();
            showToast('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.', 'error');
          }
          throw new Error('Phiên đăng nhập đã hết hạn.');
        }
        if (res.status === 403) {
          throw new Error('Bạn không có quyền thực hiện thao tác này.');
        }
        if (!res.ok) throw new Error(`Xóa khỏi Yêu thích thất bại (HTTP ${res.status})`);

        const json = await res.json();
        if (timeoutId) {
          clearTimeout(timeoutId);
          timeoutId = null;
        }

        if (!json || json.success !== true) throw new Error('Phản hồi từ máy chủ không hợp lệ.');

        if (isStillCurrentSession()) {
          const op = operationsJournalRef.current.get(opKey);
          if (op && op.id === opId) {
            op.status = 'committed';
            op.committedAtReadVersion = readGenRef.current;
          }
          showToast(`Đã xóa ${displayTitle} khỏi Yêu thích`, 'info');
          return true;
        }
        return false;
      } else {
        const res = await fetch(`${SPRINGBOOT_API}/users/favorites`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            Accept: 'application/json',
          },
          body: JSON.stringify({
            movieId: id,
            movieTitle: displayTitle,
            posterUrl: poster || '',
          }),
          signal: abortCtrl.signal,
        });

        if (res.status === 401) {
          if (isStillCurrentSession()) {
            handleSessionExpired();
            showToast('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.', 'error');
          }
          throw new Error('Phiên đăng nhập đã hết hạn.');
        }
        if (res.status === 403) {
          throw new Error('Bạn không có quyền thực hiện thao tác này.');
        }
        if (!res.ok) throw new Error(`Lưu vào Yêu thích thất bại (HTTP ${res.status})`);

        const json = await res.json();
        if (timeoutId) {
          clearTimeout(timeoutId);
          timeoutId = null;
        }

        if (!json || json.success !== true) throw new Error('Phản hồi từ máy chủ không hợp lệ.');

        if (isStillCurrentSession()) {
          const op = operationsJournalRef.current.get(opKey);
          if (op && op.id === opId) {
            op.status = 'committed';
            op.committedAtReadVersion = readGenRef.current;
          }
          showToast(`Đã thêm ${displayTitle} vào Yêu thích`, 'success');
          return true;
        }
        return false;
      }
    } catch (err: unknown) {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      if (isStillCurrentSession()) {
        const isTimeout =
          (err instanceof DOMException && err.name === 'AbortError') ||
          (err as any)?.name === 'AbortError';
        const isNetworkError =
          err instanceof TypeError || (err as any)?.name === 'TypeError';

        if (isTimeout || isNetworkError) {
          const op = operationsJournalRef.current.get(opKey);
          if (op && op.id === opId) {
            op.status = 'uncertain';
          }
          showToast('Thời gian gửi yêu cầu quá hạn hoặc mất kết nối. Đang kiểm tra lại trạng thái...', 'error');
          performFetchLibrary({ isBackgroundReconcile: true });
        } else {
          const op = operationsJournalRef.current.get(opKey);
          if (op && op.id === opId) {
            operationsJournalRef.current.delete(opKey);
          }
          setSnapshot((prev) => {
            if (prev.ownerKey !== mutationActorKey) return prev;
            return {
              ...prev,
              favorites: alreadyInFavorites
                ? (prev.favorites.includes(id) ? prev.favorites : [...prev.favorites, id])
                : prev.favorites.filter((item) => item !== id),
            };
          });
          showToast('Không thể cập nhật Yêu thích. Vui lòng thử lại.', 'error');
        }
      }
      return false;
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      activeMutationAbortControllersRef.current.delete(opId);
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
    }
  };

  // Rating Mutation
  const rateMovie = async (
    id: string,
    rating: number,
    title?: string
  ): Promise<boolean> => {
    const validRating = Math.max(1, Math.min(10, Math.round(rating)));
    const mutationActorKey = currentActorKey;
    const mutationSessionGen = sessionGenRef.current;
    const lockKey = `${mutationSessionGen}:${mutationActorKey}:rating:${id}`;
    const opKey = `rating:${id}`;

    if (syncPendingLocksRef.current.has(lockKey)) return false;
    syncPendingLocksRef.current.add(lockKey);
    setPendingUpdateTick((t) => t + 1);

    const displayTitle = title || id;
    const prevRating = visibleRatings[id];

    const isStillCurrentSession = () => {
      return (
        sessionGenRef.current === mutationSessionGen &&
        lastKnownActorKeyRef.current === mutationActorKey
      );
    };

    if (status === 'checking') {
      showToast('Đang kiểm tra phiên đăng nhập, vui lòng đợi...', 'info');
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
      return false;
    }
    if (status === 'unavailable') {
      showToast('Dịch vụ xác thực tạm thời không khả dụng. Vui lòng thử lại sau.', 'error');
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
      return false;
    }

    // 1. Guest Mode
    if (status === 'guest' || !isAuthenticated || !token) {
      const nextRatings = { ...visibleRatings, [id]: validRating };
      const saved = writeGuestStorage({
        watchlist: visibleWatchlist,
        favorites: visibleFavorites,
        ratings: nextRatings,
      });

      if (!saved) {
        showToast('Không thể lưu vào bộ nhớ thiết bị.', 'error');
        syncPendingLocksRef.current.delete(lockKey);
        setPendingUpdateTick((t) => t + 1);
        return false;
      }

      setSnapshot({
        ownerKey: 'guest',
        watchlist: visibleWatchlist,
        favorites: visibleFavorites,
        ratings: nextRatings,
      });

      showToast(`Đã chấm ${displayTitle} ${validRating}/10 điểm ★ (trên thiết bị)`, 'success');
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
      return true;
    }

    // 2. Authenticated Mode
    const opId = ++operationCounterRef.current;
    operationsJournalRef.current.set(opKey, {
      id: opId,
      action: 'rating',
      movieId: id,
      readVersionAtStart: readGenRef.current,
      committedAtReadVersion: null,
      status: 'pending',
      desiredValue: validRating,
    });

    setSnapshot((prev) => {
      const isSameActor = prev.ownerKey === mutationActorKey;
      const baseRatings = isSameActor ? prev.ratings : {};
      return {
        ownerKey: mutationActorKey,
        watchlist: isSameActor ? prev.watchlist : [],
        favorites: isSameActor ? prev.favorites : [],
        ratings: { ...baseRatings, [id]: validRating },
      };
    });

    const abortCtrl = new AbortController();
    activeMutationAbortControllersRef.current.set(opId, abortCtrl);

    let timeoutId: NodeJS.Timeout | null = setTimeout(() => {
      abortCtrl.abort();
    }, REQUEST_TIMEOUT_MS);

    try {
      const res = await fetch(`${SPRINGBOOT_API}/users/ratings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          Accept: 'application/json',
        },
        body: JSON.stringify({
          movieId: id,
          rating: validRating,
        }),
        signal: abortCtrl.signal,
      });

      if (res.status === 401) {
        if (isStillCurrentSession()) {
          handleSessionExpired();
          showToast('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.', 'error');
        }
        throw new Error('Phiên đăng nhập đã hết hạn.');
      }
      if (res.status === 403) {
        throw new Error('Bạn không có quyền thực hiện thao tác này.');
      }
      if (!res.ok) throw new Error(`Lưu điểm đánh giá thất bại (HTTP ${res.status})`);

      const json = await res.json();
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }

      if (!json || json.success !== true) throw new Error('Phản hồi từ máy chủ không hợp lệ.');

      if (isStillCurrentSession()) {
        const op = operationsJournalRef.current.get(opKey);
        if (op && op.id === opId) {
          op.status = 'committed';
          op.committedAtReadVersion = readGenRef.current;
        }
        showToast(`Đã chấm ${displayTitle} ${validRating}/10 điểm ★`, 'success');
        return true;
      }
      return false;
    } catch (err: unknown) {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      if (isStillCurrentSession()) {
        const isTimeout =
          (err instanceof DOMException && err.name === 'AbortError') ||
          (err as any)?.name === 'AbortError';
        const isNetworkError =
          err instanceof TypeError || (err as any)?.name === 'TypeError';

        if (isTimeout || isNetworkError) {
          const op = operationsJournalRef.current.get(opKey);
          if (op && op.id === opId) {
            op.status = 'uncertain';
          }
          showToast('Thời gian gửi yêu cầu quá hạn hoặc mất kết nối. Đang kiểm tra lại trạng thái...', 'error');
          performFetchLibrary({ isBackgroundReconcile: true });
        } else {
          const op = operationsJournalRef.current.get(opKey);
          if (op && op.id === opId) {
            operationsJournalRef.current.delete(opKey);
          }
          setSnapshot((prev) => {
            if (prev.ownerKey !== mutationActorKey) return prev;
            const nextR = { ...prev.ratings };
            if (prevRating !== undefined) {
              nextR[id] = prevRating;
            } else {
              delete nextR[id];
            }
            return { ...prev, ratings: nextR };
          });
          showToast('Không thể lưu điểm đánh giá. Vui lòng thử lại.', 'error');
        }
      }
      return false;
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      activeMutationAbortControllersRef.current.delete(opId);
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
    }
  };

  // Remove Rating Mutation
  const removeRating = async (id: string, title?: string): Promise<boolean> => {
    const mutationActorKey = currentActorKey;
    const mutationSessionGen = sessionGenRef.current;
    const lockKey = `${mutationSessionGen}:${mutationActorKey}:rating:${id}`;
    const opKey = `rating:${id}`;

    if (syncPendingLocksRef.current.has(lockKey)) return false;
    syncPendingLocksRef.current.add(lockKey);
    setPendingUpdateTick((t) => t + 1);

    const displayTitle = title || id;
    const prevRating = visibleRatings[id];

    const isStillCurrentSession = () => {
      return (
        sessionGenRef.current === mutationSessionGen &&
        lastKnownActorKeyRef.current === mutationActorKey
      );
    };

    if (status === 'checking') {
      showToast('Đang kiểm tra phiên đăng nhập, vui lòng đợi...', 'info');
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
      return false;
    }
    if (status === 'unavailable') {
      showToast('Dịch vụ xác thực tạm thời không khả dụng. Vui lòng thử lại sau.', 'error');
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
      return false;
    }

    // 1. Guest Mode
    if (status === 'guest' || !isAuthenticated || !token) {
      const nextRatings = { ...visibleRatings };
      delete nextRatings[id];
      const saved = writeGuestStorage({
        watchlist: visibleWatchlist,
        favorites: visibleFavorites,
        ratings: nextRatings,
      });

      if (!saved) {
        showToast('Không thể lưu vào bộ nhớ thiết bị.', 'error');
        syncPendingLocksRef.current.delete(lockKey);
        setPendingUpdateTick((t) => t + 1);
        return false;
      }

      setSnapshot({
        ownerKey: 'guest',
        watchlist: visibleWatchlist,
        favorites: visibleFavorites,
        ratings: nextRatings,
      });

      showToast(`Đã xóa đánh giá của ${displayTitle} (trên thiết bị)`, 'info');
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
      return true;
    }

    // 2. Authenticated Mode
    const opId = ++operationCounterRef.current;
    operationsJournalRef.current.set(opKey, {
      id: opId,
      action: 'rating',
      movieId: id,
      readVersionAtStart: readGenRef.current,
      committedAtReadVersion: null,
      status: 'pending',
      desiredValue: undefined,
    });

    setSnapshot((prev) => {
      const isSameActor = prev.ownerKey === mutationActorKey;
      const baseRatings = isSameActor ? { ...prev.ratings } : {};
      delete baseRatings[id];
      return {
        ownerKey: mutationActorKey,
        watchlist: isSameActor ? prev.watchlist : [],
        favorites: isSameActor ? prev.favorites : [],
        ratings: baseRatings,
      };
    });

    const abortCtrl = new AbortController();
    activeMutationAbortControllersRef.current.set(opId, abortCtrl);

    let timeoutId: NodeJS.Timeout | null = setTimeout(() => {
      abortCtrl.abort();
    }, REQUEST_TIMEOUT_MS);

    try {
      const res = await fetch(`${SPRINGBOOT_API}/users/ratings/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/json',
        },
        signal: abortCtrl.signal,
      });

      if (res.status === 401) {
        if (isStillCurrentSession()) {
          handleSessionExpired();
          showToast('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.', 'error');
        }
        throw new Error('Phiên đăng nhập đã hết hạn.');
      }
      if (res.status === 403) {
        throw new Error('Bạn không có quyền thực hiện thao tác này.');
      }
      if (!res.ok) throw new Error(`Xóa đánh giá thất bại (HTTP ${res.status})`);

      const json = await res.json();
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }

      if (!json || json.success !== true) throw new Error('Phản hồi từ máy chủ không hợp lệ.');

      if (isStillCurrentSession()) {
        const op = operationsJournalRef.current.get(opKey);
        if (op && op.id === opId) {
          op.status = 'committed';
          op.committedAtReadVersion = readGenRef.current;
        }
        showToast(`Đã xóa đánh giá của ${displayTitle}`, 'info');
        return true;
      }
      return false;
    } catch (err: unknown) {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      if (isStillCurrentSession()) {
        const isTimeout =
          (err instanceof DOMException && err.name === 'AbortError') ||
          (err as any)?.name === 'AbortError';
        const isNetworkError =
          err instanceof TypeError || (err as any)?.name === 'TypeError';

        if (isTimeout || isNetworkError) {
          const op = operationsJournalRef.current.get(opKey);
          if (op && op.id === opId) {
            op.status = 'uncertain';
          }
          showToast('Thời gian gửi yêu cầu quá hạn hoặc mất kết nối. Đang kiểm tra lại trạng thái...', 'error');
          performFetchLibrary({ isBackgroundReconcile: true });
        } else {
          const op = operationsJournalRef.current.get(opKey);
          if (op && op.id === opId) {
            operationsJournalRef.current.delete(opKey);
          }
          setSnapshot((prev) => {
            if (prev.ownerKey !== mutationActorKey) return prev;
            const nextR = { ...prev.ratings };
            if (prevRating !== undefined) {
              nextR[id] = prevRating;
            }
            return { ...prev, ratings: nextR };
          });
          showToast(`Không thể xóa đánh giá của ${displayTitle}. Vui lòng thử lại.`, 'error');
        }
      }
      return false;
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      activeMutationAbortControllersRef.current.delete(opId);
      syncPendingLocksRef.current.delete(lockKey);
      setPendingUpdateTick((t) => t + 1);
    }
  };

  const isWatchlisted = useCallback((id: string) => visibleWatchlist.includes(id), [visibleWatchlist]);
  const isFavorite = useCallback((id: string) => visibleFavorites.includes(id), [visibleFavorites]);
  const getRating = useCallback((id: string) => visibleRatings[id], [visibleRatings]);

  const openChat = () => setIsChatOpen(true);
  const closeChat = () => setIsChatOpen(false);
  const toggleChat = () => setIsChatOpen((prev) => !prev);

  return (
    <WatchlistContext.Provider
      value={{
        watchlist: visibleWatchlist,
        favorites: visibleFavorites,
        ratings: visibleRatings,
        toggleWatchlist,
        toggleFavorite,
        rateMovie,
        removeRating,
        isWatchlisted,
        isFavorite,
        getRating,
        isActionPending,
        isActionUnconfirmed,
        getActionIntent,
        getUnconfirmedRating,
        isLibraryLoading,
        libraryError,
        refetchLibrary: () => performFetchLibrary(),
        isGuestMode: status === 'guest',
        toasts,
        showToast,
        dismissToast,
        isChatOpen,
        openChat,
        closeChat,
        toggleChat,
      }}
    >
      {children}

      {/* Global Auth Modal */}
      <AuthModal />

      {/* Global CineBot Widget & Modal */}
      {!isChatOpen && <CineBotFloatingTrigger onClick={openChat} />}
      <CineBot isOpen={isChatOpen} onClose={closeChat} />

      {/* Global Toast Container */}
      <div
        role="region"
        aria-label="Thông báo hệ thống"
        className="fixed bottom-20 right-6 z-50 flex flex-col gap-2 pointer-events-none sm:bottom-6 sm:right-36"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className={`pointer-events-auto flex items-center justify-between gap-3 rounded-lg border px-4 py-2.5 text-xs sm:text-sm font-medium shadow-2xl backdrop-blur-xl animate-slide-up transition-all ${
              toast.type === 'error'
                ? 'border-red-500/50 bg-surface/95 text-red-300 shadow-red-900/20'
                : toast.type === 'success'
                ? 'border-brand/50 bg-surface/95 text-white shadow-brand-sm'
                : 'border-surface-border bg-surface/95 text-zinc-300'
            }`}
          >
            <span>{toast.message}</span>
            <button
              onClick={() => dismissToast(toast.id)}
              className="ml-2 text-zinc-400 hover:text-white cursor-pointer"
              aria-label="Đóng thông báo"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  const context = useContext(WatchlistContext);
  if (!context) {
    throw new Error('useWatchlist must be used within a WatchlistProvider');
  }
  return context;
}
