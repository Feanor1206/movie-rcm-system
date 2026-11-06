# M1 — Account & Library Contract Specification

> **Milestone:** M1 — Real Authentication and Isolated Personal Library (AUTH-01 + LIB-01 + LIB-02)  
> **Status:** Ratified Implementation Contract  
> **Backend Base URL:** `http://localhost:8080/api` (`SPRINGBOOT_API`)

---

## 1. Authentication Contract (AUTH-01)

### 1.1 Session States
The frontend authentication state machine strictly supports four distinct states:
1. `guest`: No active session credentials on device, or user explicitly logged out. Client-side features operate in guest mode.
2. `checking`: Device holds a stored JWT token; an asynchronous verification request to `GET /api/auth/me` is currently in flight. Protected actions are blocked from claiming verified status until verification completes.
3. `authenticated`: Active JWT token verified by backend `/api/auth/me` or freshly minted via successful `login`/`register`. Identity and token are guaranteed from the same session generation.
4. `unavailable`: Backend `/api/auth/me` failed due to network unreachable, timeout, or 5xx server error. Stored credentials may be retained for user-initiated retry, but UI does NOT treat user as verified.

### 1.2 Auth Endpoints

#### POST `/api/auth/login`
- **Request Body (`application/json`):**
  ```json
  {
    "usernameOrEmail": "string (trimmed username or email)",
    "password": "string (RAW verbatim password, never trimmed or lowercased)"
  }
  ```
- **Success Response (200 OK):**
  ```json
  {
    "success": true,
    "message": "Login successful",
    "data": {
      "token": "eyJhbGciOi...",
      "type": "Bearer",
      "id": 1,
      "username": "alex",
      "email": "alex@dippie.com",
      "fullName": "Alex Morgan",
      "role": "ROLE_ADMIN"
    },
    "timestamp": "2026-10-13T15:30:00"
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: Validation failure (blank field).
  - `401 Unauthorized`: Bad credentials. Message: `"Tên đăng nhập hoặc mật khẩu không chính xác"`.
  - `5xx / Network`: Service unavailable. No mock session created.

#### POST `/api/auth/register`
- **Request Body (`application/json`):**
  ```json
  {
    "username": "string (3-50 chars, alphanumeric/underscore)",
    "email": "string (valid email format)",
    "password": "string (RAW verbatim password, min 6 chars)",
    "fullName": "string (optional)"
  }
  ```
- **Success Response (200 OK):** Same structure as login `AuthResponse`.
- **Error Responses:**
  - `400 Bad Request`: Validation failure or existing username/email conflict (`"Username is already taken!"` / `"Email is already in use!"`).

#### GET `/api/auth/me`
- **Headers:** `Authorization: Bearer <token>`
- **Success Response (200 OK):**
  ```json
  {
    "success": true,
    "message": "User profile fetched successfully",
    "data": {
      "id": 1,
      "username": "alex",
      "email": "alex@dippie.com",
      "fullName": "Alex Morgan",
      "role": "ROLE_ADMIN"
    },
    "timestamp": "2026-10-13T15:30:00"
  }
  ```
- **Error Responses:**
  - `401 Unauthorized` / `403 Forbidden`: Token invalid, malformed, or expired. Client MUST discard stored token and transition to `guest`.
  - `5xx / Network Timeout`: Server unavailable. Client transitions to `unavailable`.

### 1.3 Generation & Stale Request Invalidation
- Each auth lifecycle transition increments an internal integer `authGenerationId`.
- An `AbortController` aborts any pending `/me`, `login`, or `register` fetch when `logout()` is called or a new login attempt begins.
- Any arriving HTTP response whose `generationId` does not match the active generation is completely discarded to prevent resurrecting an invalidated user session.

---

## 2. Personal Library Contract (LIB-01, LIB-02)

### 2.1 Storage Namespace & Actor Isolation
1. **Guest Mode:**
   - Storage key: `dippie_guest_library_v1`
   - Content:
     ```json
     {
       "watchlist": ["the-last-orbit"],
       "favorites": [],
       "ratings": { "the-last-orbit": 9 }
     }
     ```
   - Default initial state: **Empty** (no hardcoded legacy demo movies).
   - Label: `"Lưu trên thiết bị này"`.
2. **Authenticated Mode:**
   - Authoritative source of truth: Spring Boot database.
   - Owner identification: Extracted strictly from `SecurityContextHolder` / `Authentication.getPrincipal()` (`UserDetailsImpl.getId()`). The client never transmits `userId` in write payloads.
   - In-memory state: Synchronized with backend on login and refreshed on reload.
   - Actor switch guarantee: When switching from User A to Logout or User B, all in-memory library state is wiped synchronously (`watchlist: []`, `favorites: []`, `ratings: {}`). No late in-flight response from User A may mutate User B's state.
   - Empty list guarantee: When backend returns an empty list `[]`, the state becomes `[]`. No union merging with default/guest items.

### 2.2 Library Endpoints

#### Watchlist Endpoints (`/api/users/watchlist`)
- **GET `/api/users/watchlist`**
  - Headers: `Authorization: Bearer <token>`
  - Response (200 OK):
    ```json
    {
      "success": true,
      "data": [
        {
          "id": 10,
          "userId": 1,
          "movieId": "the-last-orbit",
          "movieTitle": "The Last Orbit",
          "posterUrl": "https://...",
          "addedAt": "2026-10-13T15:00:00"
        }
      ]
    }
    ```
- **POST `/api/users/watchlist`**
  - Request Body: `{"movieId": "string", "movieTitle": "string", "posterUrl": "string"}`
  - Validation: `movieId` must not be blank and must exist in catalog.
  - Idempotency: If `(userId, movieId)` already exists, backend returns existing item with 200 OK without creating duplicate.
- **DELETE `/api/users/watchlist/{movieId}`**
  - Response (200 OK): `{"success": true, "message": "Movie removed from watchlist"}`
  - Idempotency: If item does not exist, operation returns 200 OK cleanly.

#### Favorites Endpoints (`/api/users/favorites`) [NEW IN M1]
- **GET `/api/users/favorites`**
  - Headers: `Authorization: Bearer <token>`
  - Response (200 OK):
    ```json
    {
      "success": true,
      "data": [
        {
          "id": 5,
          "userId": 1,
          "movieId": "afterlight",
          "movieTitle": "Afterlight",
          "posterUrl": "https://...",
          "addedAt": "2026-10-13T15:00:00"
        }
      ]
    }
    ```
- **POST `/api/users/favorites`**
  - Request Body: `{"movieId": "string", "movieTitle": "string", "posterUrl": "string"}`
  - Validation: `movieId` must not be blank and must exist in catalog.
  - Idempotency: If `(userId, movieId)` already exists, backend returns existing record with 200 OK.
- **DELETE `/api/users/favorites/{movieId}`**
  - Response (200 OK): `{"success": true, "message": "Movie removed from favorites"}`
  - Idempotency: If item does not exist, operation returns 200 OK cleanly.

#### Ratings Endpoints (`/api/users/ratings`)
- **GET `/api/users/ratings`**
  - Headers: `Authorization: Bearer <token>`
  - Response (200 OK):
    ```json
    {
      "success": true,
      "data": [
        {
          "id": 12,
          "userId": 1,
          "movieId": "the-last-orbit",
          "rating": 9,
          "createdAt": "2026-10-13T15:00:00",
          "updatedAt": "2026-10-13T15:00:00"
        }
      ]
    }
    ```
- **POST `/api/users/ratings`**
  - Request Body: `{"movieId": "string", "rating": 1..10}`
  - Validation: `movieId` required, `rating` integer strictly between 1 and 10.
  - Idempotency: Upserts the unique row for `(userId, movieId)`.
- **DELETE `/api/users/ratings/{movieId}`** [NEW IDEMPOTENT DELETE]
  - Response (200 OK): `{"success": true, "message": "Movie rating removed successfully"}`

---

## 3. Database Schema & Migration Specification

### 3.1 Table Definition: `favorite_items`
```sql
CREATE TABLE IF NOT EXISTS favorite_items (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    movie_id VARCHAR(100) NOT NULL,
    movie_title VARCHAR(255) NOT NULL,
    poster_url VARCHAR(500),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_favorite_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_user_movie_favorite UNIQUE (user_id, movie_id)
);
```

### 3.2 Backward Compatibility & Zero Data Loss
- Existing tables `users`, `movies`, `watchlist_items`, and `movie_ratings` are fully preserved.
- Table creation uses `CREATE TABLE IF NOT EXISTS`.
- No dropping or recreating of existing user tables or columns.
- Rollback plan: Trường hợp cần rollback phiên bản ứng dụng về trước M1, dữ liệu trong bảng `favorite_items` được lưu giữ nguyên vẹn trong DB nhằm bảo toàn lịch sử tương tác của người dùng; code cũ không truy vấn bảng này mà không làm ảnh hưởng tính toàn vẹn hệ thống.

---

## 4. Catalog Validation & Concurrent Idempotency Guarantees (M1-F01)

### 4.1 Catalog Validation & Canonical Metadata (R5)
1. **Catalog Validation:**
   - Khi client gọi thêm Watchlist, Yêu thích hoặc Rating, `movieId` bắt buộc phải tồn tại trong danh mục catalog (`MovieRepository`).
   - Nếu `movieId` không tồn tại, backend từ chối với `HTTP 400 Bad Request` và body có cấu trúc:
     ```json
     {
       "success": false,
       "message": "Phim không tồn tại trong danh mục: <movieId>",
       "data": null,
       "timestamp": "..."
     }
     ```
2. **Canonical Metadata Precedence:**
   - Tiêu đề (`movieTitle`) và ảnh poster (`posterUrl`) lưu trữ luôn được lấy chuẩn xác từ catalog entity `Movie`, ngăn chặn hoàn toàn việc client gửi metadata giả mạo hoặc sai lệch.
3. **Orphan Deletion:**
   - Việc xóa mục khỏi Watchlist, Yêu thích hoặc xóa Rating vẫn cho phép xóa các bản ghi orphan cũ (ID không còn trong catalog) một cách an toàn (trả về 200 OK).

### 4.2 Concurrent Idempotency (R6)
1. **Concurrent Collision Recovery:**
   - Khi hai hoặc nhiều requests thêm cùng một phim diễn ra đồng thời (chạm barrier hoặc cùng tick), xung đột ràng buộc UNIQUE được cô lập xử lý an toàn bằng `LibraryPersistenceHelper` (`@Transactional(propagation = Propagation.REQUIRES_NEW)`).
   - Ngoại lệ `DataIntegrityViolationException` được bắt tại tầng service mà không làm dirty outer transaction, truy vấn lại bản ghi hiện có và phản hồi `200 OK` đồng nhất.
2. **Concurrent Rating Policy:**
   - Chấm điểm đồng thời áp dụng chính sách ghi đè hợp lệ (last-write-wins), đảm bảo duy nhất 1 bản ghi rating cho mỗi cặp `(userId, movieId)` và luôn phản hồi `200 OK`.

---

## 5. Lifecycle, State Ownership & Outcome Guarantees (M1-F02)

### 5.1 State Ownership during Render (F2)
- State thư viện cá nhân được gắn nhãn sở hữu (`snapshot.ownerKey`).
- Dữ liệu hiển thị (`visibleWatchlist`, `visibleFavorites`, `visibleRatings`) cùng các selectors và bộ đếm (counts) được tính toán trực tiếp trong quá trình render (derived values).
- Khi phiên đổi từ User A sang User B hoặc sang Guest, render đầu tiên của User B/Guest lập tức phản ánh mảng rỗng `[]` (hoặc dữ liệu guest tương ứng), tuyệt đối không để lộ dữ liệu của User A trước khi các passive `useEffect` được kích hoạt.

### 5.2 Tách biệt Session Lifecycle và Read Generation (F3)
- Vòng đời phiên (`sessionGenRef`) chỉ tăng khi danh tính người dùng thực sự thay đổi (đăng nhập, đăng xuất, chuyển tài khoản).
- Các thao tác đọc lại cùng phiên (`refetchLibrary`) tăng thế hệ đọc (`readGenRef`) riêng biệt, không làm gián đoạn, hủy bỏ hoặc kẹt trạng thái pending của các mutations đang thực thi cùng phiên.
- Phản hồi đọc thư viện tự động hòa giải (reconcile) bảo lưu các mục đang trong quá trình mutation lạc quan (optimistic) của phiên hiện hành.

### 5.3 Cô lập Side Effects & Actor Locks (F1)
- Khóa gửi đồng bộ (`syncPendingLocksRef`) được phân vùng theo khóa actor (`actorKey:movieId:action`), ngăn chặn việc thao tác `finally` của User A giải phóng khóa của User B đối với cùng một tác phẩm.
- Mọi side effects (kể cả callback `401` hết hạn phiên và toasts) được guard nghiêm ngặt; phản hồi trễ của User A không thể kích hoạt `handleSessionExpired()` hay logout User B.
- Mọi controllers của các mutations đang gửi được tự động abort khi phiên thay đổi hoặc component unmount.

### 5.4 Timeout bao trùm Body Parsing & Hòa giải Unknown Outcomes (F4)
- Bộ đếm thời gian timeout (7000ms) bao trùm cả quá trình nhận HTTP headers và phân tích cú pháp body JSON.
- Khi một write mutation bị quá hạn (timeout) hoặc mất kết nối sau khi gửi, client không khẳng định server chưa ghi; hệ thống kích hoạt hòa giải ngầm tự động (`reconcileAuthoritativeLibrary`) với backend để đồng bộ chính xác trạng thái thực tế.

### 5.5 Backend Integrity Recovery nghiêm ngặt (F5)
- Khi bắt `DataIntegrityViolationException`, backend chỉ trả về `200 OK` khi và chỉ khi tìm thấy bản ghi đã được lưu trữ thực sự trong cơ sở dữ liệu (`id != null` và `id > 0`).
- Nếu không tìm thấy bản ghi persisted, backend không được trả về object bộ nhớ tạm thời mà ném lỗi có cấu trúc (`409 Conflict`), ngăn chặn hoàn toàn việc xác nhận thành công giả tạo.

---

## 6. Snapshot Lifecycle, Mutation Journal & Ordering Policies (M1-F03)

### 6.1 Snapshot Lifecycle across Authentication Transitions (G1)
- Khóa định danh phiên mang đầy đủ token và trạng thái (`user:{userId}:{token}` cho authenticated, `guest` cho khách, `status:{status}` cho các trạng thái chuyển tiếp).
- Khi quá trình xác thực hoàn tất (`status: checking` → `authenticated`), hoặc người dùng đăng nhập tài khoản mới (Guest → A, A → Logout → B, Retry unavailable → Authenticated), phản hồi thư viện hợp lệ từ máy chủ được cam kết (commit) vào snapshot với nhãn sở hữu mới (`ownerKey: thisActorKey`), ngay cả khi snapshot trước đó thuộc về `status: checking`, `guest` hoặc tài khoản cũ.
- Render đồng bộ tính toán dựa trên `snapshot.ownerKey === currentActorKey`:
  - Tại render #1 khi vừa chuyển tài khoản (trước khi passive effects hay fetch hoàn thành): giao diện lập tức nhận danh sách rỗng `[]` (hoặc dữ liệu guest), tuyệt đối không để lộ dữ liệu của tài khoản cũ.
  - Khi phản hồi của tài khoản mới về: snapshot cập nhật thành công mang `ownerKey` mới và giao diện hiển thị đúng dữ liệu đã lưu của tài khoản mới mà không bị rơi vào trạng thái rỗng giả tạo.

### 6.2 Mutation Journal Overlay & Read/Write Ordering (G2)
- Hệ thống áp dụng sổ nhật ký thao tác có cấu trúc (`operationsJournalRef: Map<string, OperationRecord>`), theo dõi từng tác vụ mutation với metadata đầy đủ (`action`, `movieId`, `readVersionAtStart`, `status: pending | committed`, `desiredValue`).
- Khóa nhật ký được định danh trực tiếp theo định dạng `${action}:${movieId}` mà không bẻ chuỗi (split) theo dấu hai chấm, bảo đảm an toàn tuyệt đối với mọi ID phim chứa ký tự đặc biệt.
- **Quy tắc phối hợp Read / Write Ordering:**
  1. Khi một phản hồi đọc (read / refresh) phiên bản $R$ về tới client:
     - Với mỗi mục trên máy chủ: nếu mục đó có một mutation mới hơn ($readVersionAtStart \ge R$) hoặc đang ở trạng thái `pending`, client tuân theo `desiredValue` của mutation đó thay vì dữ liệu cũ từ server.
     - Với các mục đã được thêm bởi mutation mới hơn ($desiredValue = true$): mục được bảo lưu trong danh sách hiển thị, ngăn chặn tình trạng refresh cũ ghi đè làm mất tác phẩm vừa thêm.
     - Với các mục đã bị xóa bởi mutation mới hơn ($desiredValue = false$): mục không được đưa vào danh sách hiển thị, ngăn chặn tình trạng refresh cũ đưa tác phẩm đã xóa quay trở lại.
     - Với đánh giá sao: điểm số mới nhất hoặc trạng thái đã gỡ điểm được bảo vệ trọn vẹn trước phản hồi đọc cũ.
  2. Khi phiên bản đọc mới hơn ($readVersionAtStart < R$) xuất hiện sau khi mutation đã hoàn tất (`status: committed`): mutation đó được dọn dẹp sạch sẽ khỏi nhật ký (prune) vì dữ liệu máy chủ đã phản ánh trạng thái chuẩn xác.
  3. Khi thao tác mutation thất bại (rollback): bản ghi nhật ký tương ứng bị xóa lập tức, bảo đảm tính độc lập giữa các tác phẩm (thất bại của X không ảnh hưởng đến thành công của Y).

### 6.3 Hợp nhất Read & Background Reconcile với Unknown Outcomes (G3)
- Quá trình đọc thư viện chủ động (`loadLibraryForCurrentActor`) và hòa giải nền (`reconcileAuthoritativeLibrary`) được hợp nhất hoàn toàn qua một luồng xử lý duy nhất (`performFetchLibrary`):
  - Dùng chung cơ chế bảo vệ phiên (`sessionGenRef` và `lastKnownActorKeyRef` kiểm tra sau mỗi await).
  - Dùng chung thế hệ đọc (`readGenRef`) và bộ đếm thời gian timeout (7000ms) bao trùm cả fetch headers và đọc body JSON.
  - Dùng chung chính sách hòa giải nhật ký thao tác G2.
- **Xử lý Unknown Write Outcomes:**
  - Khi một yêu cầu ghi (write mutation) gặp lỗi ngắt kết nối mạng (`TypeError / Failed to fetch`) hoặc timeout (`AbortError`), kết quả ghi có thể đã được commit trên backend: client không thực hiện rollback đảo chiều mù quáng ngay lập tức.
  - Client kích hoạt hòa giải ngầm tự động có giới hạn (`performFetchLibrary({ isBackgroundReconcile: true })`) để lấy lại sự thật từ máy chủ mà không làm gián đoạn trải nghiệm người dùng, đồng thời thông báo trạng thái trung thực qua toast.
- **Khóa thao tác và Phản hồi Stale:**
  - Khóa đồng bộ mang thế hệ phiên: `${sessionGen}:${actorKey}:${action}:${movieId}`. Khối `finally` của một thao tác từ phiên cũ không bao giờ giải phóng khóa của phiên mới.
  - Mọi mutation chỉ trả về `true` khi và chỉ khi phiên vẫn còn hiệu lực (`isStillCurrentSession()`) và server xác nhận thành công. Mọi phản hồi stale từ phiên trước tự động trả về `false` và không gây ra bất kỳ side effect nào.

---

## 7. Commit Watermarking, Read Acknowledgment & Uncertain Retry Lifecycle (M1-F04)

### 7.1 Commit Watermarking & Strict Read Acknowledgment (H1)
1. **Theo dõi thời điểm commit (`committedAtReadVersion`):**
   - Bản ghi `OperationRecord` được bổ sung trường `committedAtReadVersion: number | null` (khởi tạo `null` khi bắt đầu mutation và được gán `readGenRef.current` ngay khi mutation commit thành công trên backend).
2. **Quy tắc công nhận đọc (Read Acknowledgment):**
   - Một yêu cầu đọc thư viện (refresh / refetch) phiên bản $R$ chỉ được phép công nhận (acknowledge) và ghi đè trạng thái của một mutation đã commit khi và chỉ khi yêu cầu đọc đó được khởi tạo **sau thời điểm mutation hoàn tất commit**:
     $$R > \text{op.committedAtReadVersion}$$
   - Nếu $R \le \text{op.committedAtReadVersion}$ (yêu cầu đọc được gửi đi trước hoặc trong lúc mutation đang ghi trên server, nhưng phản hồi của đọc lại về sau commit của mutation): client nhận diện phản hồi đọc này mang dữ liệu cũ từ server trước khi commit có hiệu lực. Do đó, client **bắt buộc áp dụng lớp phủ lạc quan** (`op.desiredValue`) đè lên dữ liệu cũ từ server, ngăn chặn tuyệt đối tình trạng refresh cũ xóa mất dữ liệu vừa ghi thành công.
3. **Cơ chế Prune an toàn:**
   - Việc xóa bản ghi khỏi sổ nhật ký (`operationsJournalRef.delete`) chỉ được thực hiện khi $R > \text{op.committedAtReadVersion}$. Nếu chưa có lượt đọc nào đủ mới hơn thời điểm commit, bản ghi được giữ lại để tiếp tục bảo vệ dữ liệu client trước bất kỳ phản hồi đọc trễ nào.

### 7.2 Quản lý vòng đời Uncertain & Bảo toàn ý định thao tác khi Retry (H2)
1. **Trạng thái thao tác bất định (`status: 'uncertain'`):**
   - Khi một mutation ghi gặp sự cố mạng (`TypeError / Failed to fetch`) hoặc timeout (`AbortError`), yêu cầu có thể đã được commit vào DB backend nhưng phản hồi HTTP headers bị thất lạc trước khi tới client.
   - Thao tác KHÔNG bị xóa khỏi `operationsJournalRef` và KHÔNG tự động đảo chiều rollback dữ liệu trên giao diện. Thay vào đó, bản ghi được chuyển sang trạng thái:
     `status: 'uncertain'`
   - Khóa đồng bộ (`syncPendingLocksRef`) được giải phóng trong `finally` để người dùng không bị kẹt spinner vô tận (`isActionPending` trả về `false`), đồng thời hàm `isActionUnconfirmed` phản ánh `true` để giao diện/bộ quản lý nhận biết trạng thái chưa xác nhận.
2. **Bảo toàn ý định khi thử lại (Retry Intent Preservation):**
   - Khi người dùng bấm thử lại thao tác (ví dụ: nhấn lại nút Watchlist / Yêu thích sau khi mạng chập chờn):
     - Hàm thao tác kiểm tra sự tồn tại của bản ghi `existingOp` trong nhật ký.
     - Nếu `existingOp.status === 'uncertain'`, hướng hành động `isAdding` (hoặc `targetRating`) **bảo lưu nguyên vẹn ý định ban đầu** (`existingOp.desiredValue`), **tuyệt đối không dựa trên trạng thái hiển thị lạc quan để tự động đảo chiều**:
       - Thao tác thêm (Add) ban đầu gặp sự cố mất phản hồi $\rightarrow$ Khi retry, hệ thống tiếp tục gửi `POST` (idempotent), **không tự ý đổi thành `DELETE`** làm xóa mất dữ liệu trên backend.
       - Thao tác xóa (Remove) ban đầu gặp sự cố mất phản hồi $\rightarrow$ Khi retry, hệ thống tiếp tục gửi `DELETE`, **không tự ý đổi thành `POST`** làm hồi sinh dữ liệu.
3. **Quy tắc giải quyết trạng thái Uncertain khi Background Reconcile:**
   - Khi hòa giải ngầm hoàn tất với thế hệ đọc $R > \text{op.readVersionAtStart}$:
     - Nếu dữ liệu server xác nhận mục tồn tại phù hợp với `desiredValue === true`: bản ghi chuyển từ `uncertain` sang `committed` với `committedAtReadVersion = R`.
     - Nếu dữ liệu server xác nhận mục không tồn tại sau khi đọc đủ mới: bản ghi `uncertain` được dọn dẹp và giao diện hòa giải về trạng thái thực tế của server.
     - Nếu phản hồi đọc cũ ($R \le \text{op.readVersionAtStart}$) về trễ: phản hồi đó bị coi là quá cũ để kết luận và không được phép xóa bản ghi `uncertain`.



### 7.3 UI Consumer Specifications for Uncertain Lifecycle (M1-F05)
1. **Mở rộng Context API cho UI Consumers:**
   - `isActionUnconfirmed(movieId: string, action: 'watchlist' | 'favorite' | 'rating'): boolean`: Trả về `true` khi thao tác trên phim đó đang ở trạng thái `uncertain` (timeout/mất kết nối và chưa được xác nhận bởi reconcile).
   - `getActionIntent(movieId: string, action: 'watchlist' | 'favorite' | 'rating'): 'add' | 'remove' | 'rate' | 'remove_rating' | null`: Truy vấn trực tiếp ý định thực tế của thao tác bất định:
     - Watchlist / Favorite: trả về `'add'` nếu `desiredValue === true` (thao tác trước đó là thêm), `'remove'` nếu `desiredValue === false` (thao tác trước đó là xóa).
     - Rating: trả về `'rate'` nếu `desiredValue` là số điểm (1..10), `'remove_rating'` nếu `desiredValue === undefined`.
   - `getUnconfirmedRating(movieId: string): number | undefined`: Lấy điểm số rating bất định đang chờ xác nhận hoặc retry.

2. **Nguyên tắc hiển thị & Tương tác tại UI Consumers:**
   - **Không đảo chiều nhãn giao diện dựa trên optimistic state:** Khi thao tác đang ở trạng thái `uncertain`, nhãn nút, `aria-label`, tiêu đề gợi ý (`title`) và icon bắt buộc phải khớp chính xác với hành động mạng sẽ diễn ra khi người dùng click:
     - Khi intent là `'add'` (sẽ gửi `POST` để thử lưu lại): Nút hiển thị nhãn thử lưu lại kèm badge "Chưa xác nhận", tuyệt đối **không hiển thị "Xóa"**.
     - Khi intent là `'remove'` (sẽ gửi `DELETE` để thử xóa lại): Nút hiển thị nhãn thử xóa lại kèm badge "Chưa xác nhận", tuyệt đối **không hiển thị "Thêm"**.
   - **Màu sắc và Biểu tượng nhận diện:** Sử dụng tone cảnh báo hổ phách (`amber-400 / amber-500`) kết hợp biểu tượng đồng bộ xoay `<RefreshCw>` thay cho icon toggle thông thường để người dùng nhận biết rõ ràng thao tác cần xác nhận lại.
   - **Phục hồi trạng thái bình thường (Normal Toggle):** Khi reconcile thành công hoặc thao tác retry được server xác nhận `200 OK`, trạng thái `uncertain` được xóa khỏi nhật ký, các nút lập tức trở về chế độ toggle bình thường mà không cần tải lại trang.

3. **Chi tiết triển khai trên từng màn hình:**
   - **MovieCard (`MovieCard.tsx`):**
     - Hiển thị badge `<span data-testid="unconfirmed-badge">Chưa xác nhận</span>` ở góc thẻ phim.
     - Nút watchlist đổi sang styling amber với biểu tượng `<RefreshCw>`.
     - `aria-label` phản ánh chính xác hành động: `"Chưa xác nhận lưu • Thử lưu lại ... vào danh sách xem"` (cho `add`) hoặc `"Chưa xác nhận xóa • Thử xóa lại ... khỏi danh sách xem"` (cho `remove`).
   - **MovieDetail (`MovieDetail.tsx`):**
     - Nút Watchlist & Favorite đổi sang border/background amber và icon `<RefreshCw>`.
     - Nút Watchlist hiển thị text rõ ràng: `"Chưa xác nhận • Thử lưu lại"` hoặc `"Chưa xác nhận • Thử xóa lại"`.
     - Khu vực Rating: Hiển thị banner riêng biệt `<div data-testid="rating-unconfirmed-banner">` thông báo `"Chưa xác nhận điểm X/10 ★ trên máy chủ"` cùng nút bấm riêng biệt `"Thử lưu lại"` (gửi lại đúng điểm `unconfirmedRatingScore`) hoặc `"Thử xóa lại"`. Nếu người dùng click chọn trực tiếp một ngôi sao khác, hệ thống tôn trọng ý định mới và gửi mutation điểm mới thay vì retry điểm cũ.
   - **ProfileOverview (`ProfileOverview.tsx`):**
     - Khi xảy ra `libraryError` (reconcile thất bại hoặc lỗi nạp thư viện), giao diện hiển thị banner cảnh báo bền vững `<div data-testid="library-error-banner">` ở phía trên, kèm nút `"Thử tải lại"` (`refetchLibrary`).
     - Dữ liệu thư viện và các tabs (Watchlist, Yêu thích, Đánh giá) bên dưới **vẫn được giữ nguyên vẹn và tương tác được**, tuyệt đối không che lấp hoặc làm biến mất toàn bộ lưới phim.
     - Các mục orphan/thiếu catalog metadata vẫn hiển thị đầy đủ badge "Chưa xác nhận" và nút retry với nhãn/aria-label chính xác theo intent.
     - Trong tab Đánh giá (Ratings) cho mọi loại dòng (found, error, orphan): khi thao tác ở trạng thái `uncertain`, nếu intent là `'rate'`, nút retry gọi `rateMovie(id, unconfirmedScore)` bảo lưu đúng điểm số cần retry (gửi lại `POST`), tuyệt đối không gọi `removeRating` (không gửi `DELETE`); nếu intent là `'remove_rating'`, nút retry gọi `removeRating(id)` (gửi `DELETE`). Khi rating đã confirmed, nút xóa gọi `removeRating(id)` để xóa điểm thông thường.
