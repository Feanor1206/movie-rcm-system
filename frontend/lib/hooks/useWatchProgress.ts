'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '@/lib/context/AuthContext';
import {
  getGuestWatchProgress,
  getWatchProgress,
  listWatchProgress,
  saveGuestWatchProgress,
  saveWatchProgress as saveWatchProgressRequest,
  WatchProgressError,
  type WatchProgressDraft,
  type WatchProgressRecord,
} from '@/lib/services/watchProgressService';

export type WatchProgressSaveReason = 'interval' | 'pause' | 'ended' | 'episode-change';

type ProgressState = {
  scopeId: string;
  records: WatchProgressRecord[];
  loading: boolean;
  error: string | null;
};

type ScopeIdentity = {
  id: string;
  generation: number;
  status: string;
  token: string | null;
};

type QueuedSave = {
  draft: WatchProgressDraft;
  scope: ScopeIdentity;
  resolve: (record: WatchProgressRecord | null) => void;
};

function upsertRecord(records: WatchProgressRecord[], record: WatchProgressRecord): WatchProgressRecord[] {
  return [record, ...records.filter((item) => item.episodeId !== record.episodeId)]
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
    .slice(0, 30);
}

export function useWatchProgress() {
  const { status, token, user, handleSessionExpired } = useAuth();
  const scopeId = status === 'guest'
    ? 'guest'
    : status === 'authenticated' && user && token
    ? `account:${user.id}:${token}`
    : status;
  const [state, setState] = useState<ProgressState>({ scopeId: '', records: [], loading: true, error: null });
  const [retryCount, setRetryCount] = useState(0);
  const identityRef = useRef<ScopeIdentity>({ id: scopeId, generation: 0, status, token });
  if (identityRef.current.id !== scopeId) {
    identityRef.current = { id: scopeId, generation: identityRef.current.generation + 1, status, token };
  }
  const controllersRef = useRef<Set<AbortController>>(new Set());
  const pendingSavesRef = useRef<Map<string, QueuedSave>>(new Map());
  const workersRef = useRef<Map<string, Promise<void>>>(new Map());
  const versionsRef = useRef<Map<string, number>>(new Map());
  const lastIntervalSaveRef = useRef<Map<string, number>>(new Map());

  const isCurrentScope = useCallback((scope: ScopeIdentity) => (
    identityRef.current.id === scope.id && identityRef.current.generation === scope.generation
  ), []);

  const abortScopeWork = useCallback(() => {
    controllersRef.current.forEach((controller) => controller.abort());
    controllersRef.current.clear();
    pendingSavesRef.current.forEach((job) => job.resolve(null));
    pendingSavesRef.current.clear();
    workersRef.current.clear();
    versionsRef.current.clear();
    lastIntervalSaveRef.current.clear();
  }, []);

  useEffect(() => {
    abortScopeWork();
    const scope = identityRef.current;
    setState({
      scopeId: scope.id,
      records: [],
      loading: status === 'checking' || status === 'authenticated',
      error: status === 'unavailable' ? 'Dịch vụ xác thực tạm thời không khả dụng.' : null,
    });

    if (status === 'checking' || status === 'unavailable') return abortScopeWork;
    if (status === 'guest') {
      const records = getGuestWatchProgress();
      if (isCurrentScope(scope)) setState({ scopeId: scope.id, records, loading: false, error: null });
      return abortScopeWork;
    }
    if (status !== 'authenticated' || !token || !user) return abortScopeWork;

    const controller = new AbortController();
    controllersRef.current.add(controller);
    listWatchProgress(token, { signal: controller.signal })
      .then((records) => {
        if (!isCurrentScope(scope)) return;
        records.forEach((record) => versionsRef.current.set(`${scope.id}:${record.episodeId}`, record.version));
        setState({ scopeId: scope.id, records, loading: false, error: null });
      })
      .catch((err: any) => {
        if (!isCurrentScope(scope) || err?.isCanceled || err?.name === 'AbortError') return;
        if (err?.status === 401) handleSessionExpired();
        setState({ scopeId: scope.id, records: [], loading: false, error: err?.message || 'Không thể tải tiến độ xem.' });
      })
      .finally(() => controllersRef.current.delete(controller));

    return abortScopeWork;
  }, [scopeId, status, token, user?.id, retryCount, abortScopeWork, isCurrentScope, handleSessionExpired]);

  const saveProgress = useCallback((
    draft: WatchProgressDraft,
    reason: WatchProgressSaveReason = 'pause'
  ): Promise<WatchProgressRecord | null> => {
    const scope = identityRef.current;
    if (reason === 'interval') {
      const now = Date.now();
      const previous = lastIntervalSaveRef.current.get(`${scope.id}:${draft.episodeId}`) || 0;
      if (now - previous < 15_000) return Promise.resolve(null);
      lastIntervalSaveRef.current.set(`${scope.id}:${draft.episodeId}`, now);
    }
    if (scope.status === 'guest') {
      try {
        const records = saveGuestWatchProgress(draft);
        const record = records.find((item) => item.episodeId === draft.episodeId) || null;
        if (isCurrentScope(scope)) setState({ scopeId: scope.id, records, loading: false, error: null });
        return Promise.resolve(record);
      } catch (err: any) {
        if (isCurrentScope(scope)) setState((prev) => ({ ...prev, error: err?.message || 'Không thể lưu tiến độ trên thiết bị.' }));
        return Promise.reject(err);
      }
    }
    if (scope.status !== 'authenticated' || !scope.token) return Promise.resolve(null);

    const queueKey = `${scope.id}:${draft.episodeId}`;


    return new Promise((resolve) => {
      const previousQueued = pendingSavesRef.current.get(queueKey);
      previousQueued?.resolve(null);
      pendingSavesRef.current.set(queueKey, { draft, scope, resolve });
      if (workersRef.current.has(queueKey)) return;

      const worker = (async () => {
        while (pendingSavesRef.current.has(queueKey)) {
          const job = pendingSavesRef.current.get(queueKey)!;
          pendingSavesRef.current.delete(queueKey);
          if (!isCurrentScope(job.scope) || !job.scope.token) {
            job.resolve(null);
            continue;
          }

          const controller = new AbortController();
          controllersRef.current.add(controller);
          try {
            const versionKey = `${job.scope.id}:${job.draft.episodeId}`;
            let expectedVersion = versionsRef.current.get(versionKey);
            if (expectedVersion === undefined) {
              const existing = await getWatchProgress(job.scope.token, job.draft.episodeId, { signal: controller.signal });
              if (!isCurrentScope(job.scope)) {
                job.resolve(null);
                continue;
              }
              expectedVersion = existing?.version ?? -1;
              if (existing) {
                versionsRef.current.set(versionKey, existing.version);
                setState((prev) => prev.scopeId === job.scope.id
                  ? { ...prev, records: upsertRecord(prev.records, existing) }
                  : prev);
              }
            }

            let record: WatchProgressRecord;
            try {
              record = await saveWatchProgressRequest(job.scope.token, job.draft.episodeId, {
                assetId: job.draft.assetId,
                positionMs: job.draft.positionMs,
              }, expectedVersion, { signal: controller.signal });
            } catch (err: any) {
              if (err?.status !== 409) throw err;
              const latest = await getWatchProgress(job.scope.token, job.draft.episodeId, { signal: controller.signal });
              if (!isCurrentScope(job.scope)) {
                job.resolve(null);
                continue;
              }
              const retryVersion = latest?.version ?? -1;
              if (latest) setState((prev) => prev.scopeId === job.scope.id
                ? { ...prev, records: upsertRecord(prev.records, latest) }
                : prev);
              versionsRef.current.set(versionKey, retryVersion);
              pendingSavesRef.current.get(queueKey)?.resolve(null);
              pendingSavesRef.current.delete(queueKey);
              throw new WatchProgressError('Tiến độ đã đổi ở cửa sổ khác. Mốc mới được giữ; lần lưu tiếp theo sẽ dùng phiên bản mới.', 409);
            }

            if (!isCurrentScope(job.scope)) {
              job.resolve(null);
              continue;
            }
            versionsRef.current.set(versionKey, record.version);
            setState((prev) => prev.scopeId === job.scope.id
              ? { ...prev, records: upsertRecord(prev.records, record), error: null }
              : prev);
            job.resolve(record);
          } catch (err: any) {
            if (isCurrentScope(job.scope) && !err?.isCanceled && err?.name !== 'AbortError') {
              if (err?.status === 401) handleSessionExpired();
              setState((prev) => prev.scopeId === job.scope.id
                ? { ...prev, error: err?.message || 'Không thể lưu tiến độ xem.' }
                : prev);
            }
            job.resolve(null);
          } finally {
            controllersRef.current.delete(controller);
          }
        }
      })();
      workersRef.current.set(queueKey, worker);
      void worker.finally(() => {
        if (workersRef.current.get(queueKey) === worker) workersRef.current.delete(queueKey);
      });
    });
  }, [handleSessionExpired, isCurrentScope]);

  const reload = useCallback(() => setRetryCount((value) => value + 1), []);
  const visibleState = state.scopeId === scopeId
    ? state
    : { scopeId, records: [] as WatchProgressRecord[], loading: status === 'checking' || status === 'authenticated', error: null };

  return {
    records: visibleState.records,
    loading: visibleState.loading,
    error: visibleState.error,
    saveProgress,
    reload,
    isGuest: status === 'guest',
  };
}
