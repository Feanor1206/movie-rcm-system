'use client';

import React, { useState, useRef } from 'react';
import {
  Upload,
  FileCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Loader2,
  RefreshCw,
  Layers,
  Database,
  ArrowRight,
  FileCode,
} from 'lucide-react';
import {
  validateCatalogPackage,
  importCatalogPackage,
  CatalogValidationResult,
  CatalogImportResponse,
} from '@/lib/services/catalogService';

interface CatalogImportModalProps {
  onClose?: () => void;
  onImportSuccess?: (response: CatalogImportResponse) => void;
}

export function CatalogImportModal({ onClose, onImportSuccess }: CatalogImportModalProps) {
  const [jsonInput, setJsonInput] = useState<string>('');
  const [fileName, setFileName] = useState<string | null>(null);
  const [parsingError, setParsingError] = useState<string | null>(null);

  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [validationResult, setValidationResult] = useState<CatalogValidationResult | null>(null);

  const [isImporting, setIsImporting] = useState<boolean>(false);
  const [importResult, setImportResult] = useState<CatalogImportResponse | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  const [isSyncingAi, setIsSyncingAi] = useState<boolean>(false);
  const [aiSyncStatus, setAiSyncStatus] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const validatedHashRef = useRef<string | null>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    setParsingError(null);
    setValidationResult(null);
    setImportResult(null);
    setImportError(null);
    validatedHashRef.current = null;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      setJsonInput(content);
    };
    reader.onerror = () => {
      setParsingError('Không thể đọc tệp JSON đã chọn.');
    };
    reader.readAsText(file);
  };

  const parseJsonSafely = () => {
    if (!jsonInput.trim()) {
      setParsingError('Vui lòng chọn tệp JSON hoặc dán nội dung catalog.');
      return null;
    }
    try {
      const parsed = JSON.parse(jsonInput);
      setParsingError(null);
      return parsed;
    } catch (err: any) {
      setParsingError(`Cú pháp JSON không hợp lệ: ${err?.message || err}`);
      return null;
    }
  };

  const handleValidate = async () => {
    const parsed = parseJsonSafely();
    if (!parsed) return;

    setIsValidating(true);
    setValidationResult(null);
    setImportResult(null);
    setImportError(null);
    validatedHashRef.current = null;

    try {
      const result = await validateCatalogPackage(parsed);
      setValidationResult(result);
      if (result.valid) {
        validatedHashRef.current = result.contentHash || 'valid_hash';
      }
    } catch (err: any) {
      setParsingError(`Lỗi kết nối máy chủ xác thực: ${err?.message || err}`);
    } finally {
      setIsValidating(false);
    }
  };

  const handleImport = async () => {
    const parsed = parseJsonSafely();
    if (!parsed) return;

    // Safety check: ensure preview was run on this exact payload
    if (!validationResult || !validationResult.valid || !validatedHashRef.current) {
      setImportError('Dữ liệu chưa được kiểm tra hoặc đã bị sửa đổi. Vui lòng nhấn "Kiểm tra & Xem trước" trước khi nhập.');
      return;
    }

    setIsImporting(true);
    setImportError(null);

    try {
      const res = await importCatalogPackage(parsed);
      setImportResult(res);
      if (onImportSuccess) {
        onImportSuccess(res);
      }
      setAiSyncStatus(
        res.indexStatus === 'READY'
          ? 'Chỉ mục AI đã sẵn sàng.'
          : 'Đã đưa vào hàng đợi Outbox. Đang đồng bộ chỉ mục AI trong nền.'
      );
    } catch (err: any) {
      setImportError(err?.message || 'Có lỗi xảy ra trong quá trình nhập dữ liệu.');
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="rounded-xl border border-surface-border bg-surface-elevated p-6 shadow-2xl">
      <div className="flex items-center justify-between border-b border-surface-border pb-4">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-lg bg-brand/10 text-brand">
            <Database size={22} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Nhập dữ liệu hoạt hình JSON (dippie.catalog.v1)</h2>
            <p className="text-xs text-zinc-400">
              Kiểm tra hợp lệ, xem trước khác biệt và nhập nguyên tử có quản lý revision.
            </p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-400 hover:bg-surface-hover hover:text-white"
          >
            ✕
          </button>
        )}
      </div>

      {/* Input Selection Area */}
      <div className="mt-5 space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="btn-secondary flex items-center gap-2 text-xs font-semibold"
          >
            <Upload size={14} />
            <span>Chọn tệp JSON...</span>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            onChange={handleFileUpload}
            className="hidden"
          />
          {fileName && (
            <span className="flex items-center gap-1.5 rounded bg-surface px-2.5 py-1 text-xs text-zinc-300 border border-surface-border">
              <FileCode size={13} className="text-brand" />
              {fileName}
            </span>
          )}
        </div>

        {/* Textarea for JSON content */}
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-400">
            Nội dung JSON của gói catalog:
          </label>
          <textarea
            value={jsonInput}
            onChange={(e) => {
              setJsonInput(e.target.value);
              setValidationResult(null);
              setImportResult(null);
              validatedHashRef.current = null;
            }}
            placeholder='Dán nội dung JSON tuân thủ schema dippie.catalog.v1 vào đây...'
            rows={8}
            data-testid="catalog-json-textarea"
            className="w-full rounded-lg border border-surface-border bg-surface p-3 font-mono text-xs text-zinc-200 placeholder-zinc-500 focus:border-brand focus:outline-none"
          />
        </div>

        {parsingError && (
          <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
            <XCircle size={16} className="shrink-0" />
            <span>{parsingError}</span>
          </div>
        )}

        {/* Actions Bar */}
        <div className="flex flex-wrap items-center gap-3 pt-2">
          <button
            data-testid="catalog-validate-button"
            type="button"
            onClick={handleValidate}
            disabled={isValidating || !jsonInput.trim()}
            className="btn-secondary flex items-center gap-2 text-xs font-bold disabled:opacity-50"
          >
            {isValidating ? (
              <>
                <Loader2 size={14} className="animate-spin text-brand" />
                <span>Đang kiểm tra...</span>
              </>
            ) : (
              <>
                <FileCheck size={14} className="text-brand" />
                <span>Kiểm tra & Xem trước</span>
              </>
            )}
          </button>

          <button
            data-testid="catalog-import-button"
            type="button"
            onClick={handleImport}
            disabled={
              isImporting ||
              !jsonInput.trim() ||
              (validationResult !== null && !validationResult.valid)
            }
            className="btn-primary flex items-center gap-2 text-xs font-bold disabled:opacity-50"
          >

            {isImporting ? (
              <>
                <Loader2 size={14} className="animate-spin text-zinc-950" />
                <span>Đang ghi vào cơ sở dữ liệu...</span>
              </>
            ) : (
              <>
                <Database size={14} />
                <span>Xác nhận nhập dữ liệu</span>
              </>
            )}
          </button>
        </div>

        {/* Validation Preview Panel */}
        {validationResult && (
          <div data-testid="catalog-validation-panel" className="mt-4 rounded-xl border border-surface-border bg-surface p-4">
            <div className="flex items-center justify-between border-b border-surface-border pb-3">
              <div className="flex items-center gap-2">
                {validationResult.valid ? (
                  <span data-testid="catalog-validation-status" className="flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-bold text-emerald-400 border border-emerald-500/30">
                    <CheckCircle2 size={14} /> Gói hợp lệ
                  </span>
                ) : (
                  <span data-testid="catalog-validation-status" className="flex items-center gap-1.5 rounded-full bg-red-500/15 px-3 py-1 text-xs font-bold text-red-400 border border-red-500/30">
                    <XCircle size={14} /> Gói không hợp lệ ({validationResult.errors.length} lỗi)
                  </span>
                )}
                {validationResult.packageId && (
                  <span className="text-xs text-zinc-400">
                    Mã gói: <strong className="text-white">{validationResult.packageId}</strong> (Rev {validationResult.revision})
                  </span>
                )}
              </div>
              {validationResult.contentHash && (
                <span className="font-mono text-[11px] text-zinc-500" title={validationResult.contentHash}>
                  SHA-256: {validationResult.contentHash.slice(0, 12)}...
                </span>
              )}
            </div>


            {/* Diffs Counters */}
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-lg bg-surface-elevated p-2.5 border border-surface-border">
                <span className="text-[11px] text-zinc-400">Tạo mới</span>
                <p className="text-base font-bold text-emerald-400">+{validationResult.toCreate}</p>
              </div>
              <div className="rounded-lg bg-surface-elevated p-2.5 border border-surface-border">
                <span className="text-[11px] text-zinc-400">Cập nhật</span>
                <p className="text-base font-bold text-amber-400">~{validationResult.toUpdate}</p>
              </div>
              <div className="rounded-lg bg-surface-elevated p-2.5 border border-surface-border">
                <span className="text-[11px] text-zinc-400">Không đổi</span>
                <p className="text-base font-bold text-zinc-300">{validationResult.unchanged}</p>
              </div>
              <div className="rounded-lg bg-surface-elevated p-2.5 border border-surface-border">
                <span className="text-[11px] text-zinc-400">Xung đột</span>
                <p className={`text-base font-bold ${validationResult.conflicts > 0 ? 'text-red-400' : 'text-zinc-500'}`}>
                  {validationResult.conflicts}
                </p>
              </div>
            </div>

            {/* Error Table if Invalid */}
            {validationResult.errors && validationResult.errors.length > 0 && (
              <div className="mt-4">
                <h4 className="mb-2 text-xs font-semibold text-red-400">Chi tiết lỗi theo JSON Pointer:</h4>
                <div className="max-h-56 overflow-y-auto rounded-lg border border-red-500/20 bg-surface-elevated text-xs">
                  <table className="w-full text-left">
                    <thead className="border-b border-surface-border bg-surface text-zinc-400">
                      <tr>
                        <th className="p-2">Vị trí (Path)</th>
                        <th className="p-2">Mã lỗi</th>
                        <th className="p-2">Mô tả</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-border font-mono text-[11px]">
                      {validationResult.errors.map((err, idx) => (
                        <tr key={idx} className="hover:bg-red-500/5">
                          <td className="p-2 text-amber-300">{err.path}</td>
                          <td className="p-2 text-zinc-400">{err.code}</td>
                          <td className="p-2 font-sans text-zinc-200">{err.message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Import Error */}
        {importError && (
          <div data-testid="catalog-import-error" className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
            <XCircle size={16} className="shrink-0" />
            <span>{importError}</span>
          </div>
        )}

        {/* Import Success Panel */}
        {importResult && (
          <div data-testid="catalog-import-success-panel" className="mt-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
            <div className="flex items-center gap-2 text-emerald-400">

              <CheckCircle2 size={18} />
              <h3 className="text-sm font-bold">Nhập dữ liệu thành công!</h3>
            </div>
            <p className="mt-1 text-xs text-zinc-300">{importResult.message}</p>

            <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-zinc-300 sm:grid-cols-4">
              {importResult.counts &&
                Object.entries(importResult.counts).map(([entity, count]) => (
                  <div key={entity} className="rounded bg-surface p-2 border border-surface-border">
                    <span className="text-[11px] text-zinc-400 capitalize">{entity}:</span>
                    <strong className="ml-1 text-white">{count}</strong>
                  </div>
                ))}
            </div>

            <div className="mt-3 flex items-center justify-between border-t border-emerald-500/20 pt-2 text-[11px] text-zinc-400">
              <span>Import ID: <code className="text-emerald-300">{importResult.importId}</code></span>
              <span>{isSyncingAi ? 'Đang đồng bộ AI...' : (aiSyncStatus || 'Chỉ mục AI sẵn sàng.')}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
