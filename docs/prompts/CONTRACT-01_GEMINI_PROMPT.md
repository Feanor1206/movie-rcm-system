# CONTRACT-01 — Contract cho bản animation discovery đầu tiên

Chỉ giao sau SERVE-01-F01 được review. Áp dụng hướng dẫn chung. Đây là ticket **thiết kế tài liệu và JSON fixtures**, không sửa runtime ứng dụng.

## Mục tiêu

Ba lớp frontend/Spring/FastAPI cùng hiểu catalog, session, structured discovery, evidence, errors và library. Chốt bản đầu đủ để người dùng chọn phim hoạt hình theo thời lượng/năm/thể loại và lưu đúng tài khoản.

## Đọc

- `frontend/types/movie.ts`, `frontend/lib/context/*`, `frontend/lib/services/chatService.ts`.
- Java Movie/MovieResponse/MovieController, ApiResponse, WatchlistRequest/RatingRequest và services.
- `database/schema/01_init.sql` và `backend/springboot/src/main/resources/schema.sql`.
- FastAPI schemas/main/pipeline và intent Phase23; không giả định adapter đã biết schema mới.
- Kế hoạch kỹ thuật và UX blueprint.

## Đầu ra

1. `docs/contracts/ANIMATION_DISCOVERY_V1.md`: normative contract và compatibility plan.
2. `docs/contracts/schemas/`: JSON Schema dùng để kiểm tra fixtures, version ghi rõ và không yêu cầu runtime codegen.
3. `docs/contracts/examples/`: success/clarification/no-results/unknown/errors, guest/account, retry/version conflict.
4. `docs/reports/CONTRACT-01_REPORT.md`: quyết định, source mapping và checklist.

## Các quyết định phải thể hiện

- Catalog: movieId chuẩn, external source IDs tách riêng, aliases, year, runtimeMinutes nullable, genres; summary không spoil, media optional, provenance/unknown, draft/published/archived, catalogVersion.
- Fields tone/technique/age-classification optional và có provenance; không bắt pilot data fill facets chưa xác minh. Rating value/scale/source/voteCount tách match score.
- `GET /api/v1/movies` và detail mới; filters combined AND, OR trong cùng multi-select genres khi semantics đó được chọn và ghi rõ; paging/sort stable, limit bounded. Legacy `/api/movies` giữ compatible cho đến cutover.
- Session cấp bởi Spring Boot, owner guest/account; guest credential giữ server-verified identity, không chỉ session ID đoán được. Session ID không thay auth token.
- Turn: query XOR structured input hoặc explicit patch; previous/session version, stable turn ID, limit; retry cùng turn ID không áp dụng lại patch. Không dùng session `default` chung.
- Internal FastAPI: caller identity, catalog/profile/session versions, bounded history/snapshot; client không gửi arbitrary catalog hoặc chọn userId của người khác.
- Structured filters basic chỉ runtime/year/exclude/include có dữ liệu. Tone/reference relative mở rộng có version sau; không tự convert sang prompt Qwen cho mọi click.
- Outcome RESULTS/NEEDS_CLARIFICATION/NO_RESULTS; infrastructure error tách riêng. Missing required metadata không coi satisfied.
- Evidence cơ bản nêu constraint statuses/sources; ordered results là movie IDs; hydration giữ order/version và revalidate publication khi stale.
- Schema intent Phase23 v1 được giữ hoặc adapter có mapping; phân biệt stable business intent với raw model output. Không hứa raw adapter đã hỗ trợ fields mới.
- Library: watched/favorite/watchlist/rating độc lập; rating 1–10; PUT/DELETE state idempotent; scope guest vs account, không tự nhập guest state khi login.
- Errors: code/requestId/message ổn định; 401/403 ownership, 409 stale version, 429 capacity, 503 unavailable, 502 invalid inference. Không trả stack traces cho UI.
- Job response 202 chỉ khi pipeline jobs được triển khai; mô tả reserved future extension, không gắn nó như endpoint đã tồn tại. Deadline/cancel scope rõ khi thiết kế tương lai.

## Nghiệm thu

- Có bảng field mapping TS/Java/Pydantic/SQL hiện hữu → contract mới và migration/backfill policy; không thực hiện migration trong ticket này.
- Fixtures có ít nhất: movie runtime unknown, published/draft, structured results, no-results, clarification, model failure, guest/account, invalid ownership, duplicated turn, stale version.
- Phân biệt synthetic test fixture khỏi factual pilot catalog. Synthetic values chỉ dùng test/example và ghi rõ.
- JSON fixtures được validate bằng JSON Schema với công cụ có sẵn; nếu thiếu validator thì ghi limitation, không nói validated.
- Giới hạn input/list/history/cache được ghi cụ thể dưới dạng constants đề xuất, không “vô hạn/tùy ý”; có reasoning và đường điều chỉnh.
- API/frontend có thể xử lý states mà không xem pipeline internals.

Dừng để review tài liệu trước khi code contract vào ứng dụng. Không tự triển khai DATA/CAT/auth/UI.
