'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Database,
  Film,
  Calendar,
  Layers,
  ArrowRight,
  Clock,
  Sparkles,
  RefreshCw,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Activity,
} from 'lucide-react';
import { CatalogImportModal } from '@/features/admin/components/CatalogImportModal';
import { useAuth } from '@/lib/context/AuthContext';
import {
  getCatalogSeriesList,
  getImportHistory,
  getCatalogSnapshots,
  retryCatalogSnapshot,
  CatalogSeriesSummary,
  CatalogImportResponse,
  CatalogSnapshot,
} from '@/lib/services/catalogService';

export default function AdminImportPage() {
  const { status, user, token, openAuthModal, retryVerify } = useAuth();
  const isAdmin = status === 'authenticated' && user?.role === 'ROLE_ADMIN' && !!token;
  const [seriesList, setSeriesList] = useState<CatalogSeriesSummary[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [snapshots, setSnapshots] = useState<CatalogSnapshot[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [refreshNonce, setRefreshNonce] = useState<number>(0);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [loadErrors, setLoadErrors] = useState({ series: false, history: false, snapshots: false });

  useEffect(() => {
    if (!isAdmin) return;
    const controller = new AbortController();
    setIsLoading(true);
    setLoadErrors({ series: false, history: false, snapshots: false });

    Promise.allSettled([
      getCatalogSeriesList(undefined, controller.signal),
      getImportHistory(undefined, controller.signal),
      getCatalogSnapshots(undefined, controller.signal),
    ]).then(([series, hist, snaps]) => {
      if (controller.signal.aborted) return;
      setSeriesList(series.status === 'fulfilled' ? series.value : []);
      setHistory(hist.status === 'fulfilled' ? hist.value : []);
      setSnapshots(snaps.status === 'fulfilled' ? snaps.value : []);
      setLoadErrors({ series: series.status === 'rejected', history: hist.status === 'rejected', snapshots: snaps.status === 'rejected' });
      setIsLoading(false);
    });

    return () => controller.abort();
  }, [refreshNonce, isAdmin, token]);

  const handleImportSuccess = (_res: CatalogImportResponse) => {
    setRefreshNonce((n) => n + 1);
  };

  const handleRetrySnapshot = async (id: string) => {
    setRetryingId(id);
    setActionMessage(null);
    try {
      const updated = await retryCatalogSnapshot(id);
      setActionMessage({
        text: `Đã kích hoạt thử lại cho Snapshot [${id}] (Thế hệ ${updated.snapshotVersion}).`,
        type: 'success',
      });
      setRefreshNonce((n) => n + 1);
    } catch (err: any) {
      setActionMessage({
        text: err?.message || `Lỗi khi thử lại snapshot [${id}]`,
        type: 'error',
      });
    } finally {
      setRetryingId(null);
    }
  };

  if (status === 'checking') return <div role="status" className="p-8 text-sm">Đang kiểm tra tài khoản…</div>;
  if (status === 'unavailable') return <div role="alert" className="p-8 text-sm">Không thể kiểm tra tài khoản. <button className="underline" onClick={() => retryVerify()}>Thử lại</button></div>;
  if (status === 'guest') return <div className="p-8 text-sm">Vui lòng đăng nhập để quản trị danh mục. <button data-testid="admin-sign-in" className="underline" onClick={() => openAuthModal('login')}>Đăng nhập</button></div>;
  if (!isAdmin) return <div data-testid="admin-forbidden" role="alert" className="p-8 text-sm">Tài khoản này không có quyền quản trị danh mục.</div>;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-surface-border pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand">
            <Database size={14} />
            <span>Quản trị danh mục</span>
          </div>
          <h1 className="mt-1 text-2xl font-extrabold text-ink sm:text-3xl">
            Nhập Dữ Liệu Hoạt Hình (dippie.catalog.v1)
          </h1>
          <p className="mt-1 text-sm text-muted">
            Nhập dữ liệu JSON từ bên ngoài, kiểm tra tính hợp lệ trước khi lưu trữ bền vững trong cơ sở dữ liệu.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setRefreshNonce((n) => n + 1)}
            className="btn-secondary flex items-center gap-1.5 text-xs font-medium text-muted"
          >
            <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
            <span>Làm mới</span>
          </button>
          <Link
            href="/search"
            className="btn-secondary flex items-center gap-1.5 text-xs font-medium text-muted"
          >
            <Film size={14} />
            <span>Xem kho phim</span>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Left 2 Cols: Import Tool */}
        <div className="lg:col-span-2 space-y-8">
          <CatalogImportModal onImportSuccess={handleImportSuccess} />

          {/* Currently Imported Series Section */}
          <div className="rounded-xl border border-surface-border bg-surface p-6 shadow-sm">
            <div className="flex items-center justify-between border-b border-surface-border pb-3">
              <div className="flex items-center gap-2">
                <Film size={18} className="text-brand" />
                <h2 className="text-base font-bold text-ink">
                  Các bộ hoạt hình đã nhập ({seriesList.length})
                </h2>
              </div>
              <span className="text-xs text-muted">Xem chi tiết các phần, tập và cảnh</span>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-10 text-xs text-muted">
                <RefreshCw size={16} className="animate-spin text-brand mr-2" />
                <span>Đang tải danh sách bộ phim...</span>
              </div>
            ) : loadErrors.series ? (
              <LoadError label="danh sách bộ phim" onRetry={() => setRefreshNonce((n) => n + 1)} />
            ) : seriesList.length === 0 ? (
              <div className="py-8 text-center text-xs text-muted">
                Chưa có bộ hoạt hình nào được nhập. Hãy tải tệp JSON lên để bắt đầu.
              </div>
            ) : (
              <div className="mt-4 divide-y divide-surface-border">
                {seriesList.map((ser) => (
                  <div
                    key={ser.id}
                    className="flex flex-wrap items-center justify-between gap-4 py-3.5 transition-colors hover:bg-surface-hover/50 rounded-lg px-2"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <Link
                          href={`/series/${encodeURIComponent(ser.id)}`}
                          className="text-sm font-bold text-ink hover:text-brand transition-colors"
                        >
                          {ser.title}
                        </Link>
                        {ser.releaseYearStart && (
                          <span className="rounded bg-surface-elevated px-1.5 py-0.5 text-[10px] text-muted border border-surface-border">
                            {ser.releaseYearStart}
                          </span>
                        )}
                        <span className="font-mono text-[11px] text-muted">
                          [{ser.id}]
                        </span>
                      </div>
                      {ser.synopsis && (
                        <p className="mt-1 line-clamp-1 text-xs text-muted max-w-xl">
                          {ser.synopsis}
                        </p>
                      )}
                    </div>

                    <Link
                      href={`/series/${encodeURIComponent(ser.id)}`}
                      className="btn-secondary flex items-center gap-1.5 text-xs font-semibold shrink-0"
                    >
                      <span>Xem tập & cảnh</span>
                      <ArrowRight size={13} />
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Action Message Banner */}
          {actionMessage && (
            <div
              className={`flex items-center justify-between gap-3 rounded-xl border p-4 text-xs ${
                actionMessage.type === 'success'
                  ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                  : 'border-red-500/30 bg-red-500/10 text-red-300'
              }`}
            >
              <div className="flex items-center gap-2">
                {actionMessage.type === 'success' ? (
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                ) : (
                  <XCircle size={16} className="text-red-400 shrink-0" />
                )}
                <span>{actionMessage.text}</span>
              </div>
              <button
                onClick={() => setActionMessage(null)}
                className="text-muted hover:text-ink"
              >
                ✕
              </button>
            </div>
          )}

          {/* Outbox Snapshots & AI Index Sync Section */}
          <div className="rounded-xl border border-surface-border bg-surface p-6 shadow-sm">
            <div className="flex items-center justify-between border-b border-surface-border pb-3">
              <div className="flex items-center gap-2">
                <Activity size={18} className="text-brand" />
                <h2 className="text-base font-bold text-ink">
                  Hàng đợi Outbox & Đồng bộ Chỉ mục AI ({snapshots.length})
                </h2>
              </div>
              <span className="text-xs text-muted">Trạng thái đồng bộ tự động giữa Spring Boot và FastAPI</span>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-8 text-xs text-muted">
                <RefreshCw size={16} className="animate-spin text-brand mr-2" />
                <span>Đang kiểm tra hàng đợi outbox...</span>
              </div>
            ) : loadErrors.snapshots ? (
              <LoadError label="trạng thái đồng bộ" onRetry={() => setRefreshNonce((n) => n + 1)} />
            ) : snapshots.length === 0 ? (
              <div className="py-6 text-center text-xs text-muted">
                Chưa có snapshot nào được tạo. Khi bạn nhập gói catalog, snapshot sẽ được ghi nhận tại đây.
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                {snapshots.map((snap) => {
                  const isRetrying = retryingId === snap.id;
                  const canRetry = snap.status === 'SYNC_FAILED' || snap.status === 'BLOCKED' || snap.status === 'PENDING';
                  return (
                    <div
                      key={snap.id}
                      className="rounded-lg border border-surface-border bg-surface-elevated p-3.5 text-xs space-y-2"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-brand">
                            Thế hệ {snap.snapshotVersion}
                          </span>
                          <span className="font-mono text-muted">[{snap.id}]</span>
                          <span className="text-muted">({snap.totalItems} mục)</span>
                        </div>

                        <div className="flex items-center gap-2">
                          {snap.status === 'READY' && (
                            <span className="flex items-center gap-1 rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] font-bold text-emerald-400 border border-emerald-500/30">
                              <CheckCircle2 size={12} /> READY (Đã chỉ mục)
                            </span>
                          )}
                          {snap.status === 'SYNCING' && (
                            <span className="flex items-center gap-1 rounded bg-blue-500/10 px-2 py-0.5 text-[11px] font-bold text-blue-400 border border-blue-500/30 animate-pulse">
                              <RefreshCw size={12} className="animate-spin" /> SYNCING (Đang đồng bộ)
                            </span>
                          )}
                          {snap.status === 'PENDING' && (
                            <span className="flex items-center gap-1 rounded bg-amber-500/10 px-2 py-0.5 text-[11px] font-bold text-amber-400 border border-amber-500/30">
                              <Clock size={12} /> PENDING (Chờ xử lý)
                            </span>
                          )}
                          {snap.status === 'BLOCKED' && (
                            <span className="flex items-center gap-1 rounded bg-orange-500/10 px-2 py-0.5 text-[11px] font-bold text-orange-400 border border-orange-500/30">
                              <AlertTriangle size={12} /> BLOCKED (Thiếu token)
                            </span>
                          )}
                          {snap.status === 'SYNC_FAILED' && (
                            <span className="flex items-center gap-1 rounded bg-red-500/10 px-2 py-0.5 text-[11px] font-bold text-red-400 border border-red-500/30">
                              <XCircle size={12} /> SYNC_FAILED (Lỗi đồng bộ)
                            </span>
                          )}

                          {canRetry && (
                            <button
                              type="button"
                              onClick={() => handleRetrySnapshot(snap.id)}
                              disabled={isRetrying}
                              className="btn-secondary flex items-center gap-1 text-[11px] py-1 px-2.5 font-semibold text-brand hover:text-ink disabled:opacity-50"
                            >
                              <RotateCcw size={11} className={isRetrying ? 'animate-spin' : ''} />
                              <span>{isRetrying ? 'Đang gửi...' : 'Thử lại'}</span>
                            </button>
                          )}
                        </div>
                      </div>

                      {snap.errorMessage && (
                        <p className="rounded bg-red-500/10 p-2 font-mono text-[11px] text-red-400 border border-red-500/20">
                          {snap.errorMessage}
                        </p>
                      )}

                      <div className="flex items-center justify-between text-[10px] text-muted font-mono">
                        <span title={snap.contentHash}>SHA-256: {snap.contentHash.slice(0, 16)}...</span>
                        {snap.retryCount !== undefined && snap.retryCount > 0 && (
                          <span>Số lần thử lại: {snap.retryCount}</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Col: Info & Import History */}
        <div className="space-y-6">
          {/* Workflow Guide Card */}
          <div className="rounded-xl border border-surface-border bg-surface p-5">
            <h3 className="flex items-center gap-2 text-sm font-bold text-ink">
              <Sparkles size={16} className="text-brand" />
              <span>Quy trình nhập dữ liệu</span>
            </h3>
            <ol className="mt-3 space-y-2.5 text-xs text-muted">
              <li className="flex gap-2">
                <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand/20 font-mono text-[11px] font-bold text-brand">
                  1
                </span>
                <span>
                  <strong>JSON bên ngoài:</strong> Chuẩn hóa theo hợp đồng{' '}
                  <code className="text-muted">dippie.catalog.v1</code>.
                </span>
              </li>
              <li className="flex gap-2">
                <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand/20 font-mono text-[11px] font-bold text-brand">
                  2
                </span>
                <span>
                  <strong>Xác thực & Preview:</strong> Kiểm tra ràng buộc tham chiếu, tính SHA-256 và diff toCreate/toUpdate.
                </span>
              </li>
              <li className="flex gap-2">
                <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand/20 font-mono text-[11px] font-bold text-brand">
                  3
                </span>
                <span>
                  <strong>Atomic Transaction:</strong> Nhập 12 bảng thực thể và ánh xạ video Google Drive vào Media Service.
                </span>
              </li>
              <li className="flex gap-2">
                <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand/20 font-mono text-[11px] font-bold text-brand">
                  4
                </span>
                <span>
                  <strong>AI Index Sync:</strong> Tự động cập nhật chỉ mục Hybrid Retrieval và CineBot.
                </span>
              </li>
            </ol>
          </div>

          {/* Import History */}
          <div className="rounded-xl border border-surface-border bg-surface p-5">
            <div className="flex items-center gap-2 border-b border-surface-border pb-3">
              <Clock size={16} className="text-brand" />
              <h3 className="text-sm font-bold text-ink">Lịch sử gói nhập</h3>
            </div>

            {isLoading ? <p role="status" className="mt-3 text-xs text-muted">Đang tải lịch sử…</p> : loadErrors.history ? (
              <div data-testid="history-error"><LoadError label="lịch sử nhập" onRetry={() => setRefreshNonce((n) => n + 1)} /></div>
            ) : history.length === 0 ? (
              <p className="mt-3 text-xs text-muted">Chưa có lịch sử nhập gói.</p>
            ) : (
              <div className="mt-3 space-y-3">
                {history.map((pkg: any) => (
                  <div
                    key={pkg.id}
                    className="rounded-lg border border-surface-border bg-surface-elevated p-3 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <strong className="text-ink font-mono">{pkg.id}</strong>
                      <span className="rounded bg-brand/10 px-1.5 py-0.5 text-[10px] font-bold text-brand border border-brand/20">
                        Rev {pkg.revision}
                      </span>
                    </div>
                    {pkg.description && (
                      <p className="mt-1 text-[11px] text-muted line-clamp-2">
                        {pkg.description}
                      </p>
                    )}
                    <div className="mt-2 flex items-center justify-between text-[10px] text-muted font-mono">
                      <span>{pkg.defaultLanguage?.toUpperCase()}</span>
                      <span title={pkg.contentHash}>
                        {pkg.contentHash ? `SHA: ${pkg.contentHash.slice(0, 10)}...` : ''}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function LoadError({ label, onRetry }: { label: string; onRetry: () => void }) {
  return <p role="alert" className="mt-3 text-xs text-red-400">Không thể tải {label}. <button className="underline" onClick={onRetry}>Thử lại</button></p>;
}
