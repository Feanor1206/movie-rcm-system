# Sổ Tay Vận Hành Hệ Thống (Operations Runbook) — Dippie Movie Recommendation System

**Phiên bản tài liệu:** 1.0  
**Áp dụng:** Milestone M3 (Môi trường Dev, Test, và Production)  
**Ngày cập nhật:** 14/10/2026

---

## 1. Yêu Cầu Môi Trường (Prerequisites)

| Thành phần | Phiên bản tối thiểu | Ghi chú |
|---|---|---|
| **Node.js** | `>= 20.x LTS` | Chạy Frontend Next.js 15 và Test suites |
| **Java JDK** | `>= 17 LTS` (khuyến nghị JDK 21/25) | Build và chạy Spring Boot backend (`JAVA_HOME`) |
| **Maven** | `>= 3.9` hoặc `mvnw` wrapper đi kèm | Quản lý dependencies backend |
| **PostgreSQL** | `>= 14` | Chỉ dùng cho môi trường `prod` (môi trường `dev` dùng H2 tự động) |

---

## 2. Cấu Hình Biến Môi Trường (Environment Configuration)

### 2.1. Frontend (`frontend/.env.local` hoặc biến môi trường container)

```bash
# URL API Backend Spring Boot
NEXT_PUBLIC_SPRINGBOOT_API_URL=http://localhost:8080/api

# Cổng lắng nghe (mặc định 3000)
PORT=3000
```

### 2.2. Backend Spring Boot (`backend/springboot`)

| Biến môi trường | Bắt buộc ở Prod? | Giá trị mặc định Dev | Mô tả |
|---|---|---|---|
| `SPRING_PROFILES_ACTIVE` | Có | `dev` | Profile hoạt động (`dev`, `test`, `prod`) |
| `SPRING_DATASOURCE_URL` | Có (prod) | `jdbc:h2:file:./data/moviercm_db...` | Chuỗi kết nối JDBC PostgreSQL |
| `SPRING_DATASOURCE_USERNAME` | Có (prod) | `sa` | Tên người dùng database |
| `SPRING_DATASOURCE_PASSWORD` | **BẮT BUỘC (prod)** | Không có (Dev rỗng) | Mật khẩu database; cấm fallback cứng |
| `APP_JWT_SECRET` | **BẮT BUỘC (prod)** | Chuỗi SHA256 mẫu dev | Khóa ký JWT; tối thiểu 256 bits |
| `APP_CORS_ALLOWED_ORIGINS` | Không | `http://localhost:3000,...` | Danh sách domain frontend được phép truy cập |

> [!CAUTION]
> **Tuyệt đối không đưa mật khẩu thật hoặc khóa JWT vào git commit, file cấu hình tĩnh hoặc log.**

---

## 3. Chính Sách Môi Trường & Dữ Liệu Khởi Tạo (Seed Policy)

Hệ thống phân tách nghiêm ngặt 3 profile:

| Tiêu chí | `dev` | `test` | `prod` |
|---|---|---|---|
| **Cơ sở dữ liệu** | H2 Persistent file (`./data/moviercm_db`) | H2 In-Memory (`mem:m1_test_db`) | PostgreSQL thực tế |
| **Hibernate DDL** | `update` (hỗ trợ phát triển nhanh) | `create-drop` (dọn dẹp sau test) | `validate` (nghiêm cấm tự đổi schema) |
| **SQL Init Mode** | `always` | `never` | `never` (không chạy SQL tự phát) |
| **Demo Accounts Seed** | `app.seed.enabled: true` (50 users mẫu) | `app.seed.enabled: false` | `app.seed.enabled: false` (CẤM nạp demo) |
| **Catalog Seed** | 6 phim mẫu cục bộ | 0 (fixture riêng từng test) | Nạp qua luồng dữ liệu chuẩn có kiểm soát |

---

## 4. Quản Lý Migration & Cơ Sở Dữ Liệu Production

### 4.1. File Schema Chuẩn
- Đường dẫn file DDL: [`docs/runbooks/db/schema_v1.sql`](file:///D:/Class/movie-rcm-system/docs/runbooks/db/schema_v1.sql)
- Các bảng quản lý: `users`, `movies`, `watchlist_items`, `favorite_items`, `movie_ratings`.

### 4.2. Áp dụng Migration trên Production
Trước khi khởi động ứng dụng với profile `prod`, quản trị viên chạy lệnh migration thủ công:
```bash
# Kiểm tra kết nối tới database
pg_isready -h <DB_HOST> -p 5432 -U <DB_USER>

# Chạy DDL schema_v1.sql
psql -h <DB_HOST> -U <DB_USER> -d movie_rcm_db -f docs/runbooks/db/schema_v1.sql
```

### 4.3. Quy Trình Rollback An Toàn (Bảo toàn dữ liệu người dùng)
Nếu cần khôi phục lại phiên bản trước:
1. **Sao lưu dữ liệu trước rollback:**
   ```bash
   pg_dump -h <DB_HOST> -U <DB_USER> -d movie_rcm_db -t users -t watchlist_items -t favorite_items -t movie_ratings > backup_user_data_$(date +%Y%m%d_%H%M%S).sql
   ```
2. **Hạ cấp có kiểm soát:** Không drop toàn bộ bảng nếu chỉ cần sửa cột; nếu rollback hoàn toàn phiên bản mới:
   ```sql
   -- Chỉ thực hiện khi có bản backup xác nhận
   DROP TABLE IF EXISTS movie_ratings;
   DROP TABLE IF EXISTS favorite_items;
   DROP TABLE IF EXISTS watchlist_items;
   -- Bảng movies và users giữ lại nếu tương thích ngược
   ```

---

## 5. Vận Hành Khởi Động & Tắt Tiến Trình (Process Management)

### 5.1. Khởi động môi trường Phát triển (Development)

**Cửa sổ 1 — Backend Spring Boot:**
```powershell
cd D:\Class\movie-rcm-system\backend\springboot
$env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"
.\mvnw.cmd spring-boot:run -Dspring-boot.run.profiles=dev
```
*Backend sẵn sàng tại `http://localhost:8080` (H2 console: `http://localhost:8080/h2-console`).*

**Cửa sổ 2 — Frontend Next.js:**
```powershell
cd D:\Class\movie-rcm-system\frontend
npm run dev
```
*Giao diện sẵn sàng tại `http://localhost:3000`.*

### 5.2. Khởi động môi trường Độc Lập / Production (Standalone Mode)
Frontend được đóng gói theo chế độ `output: 'standalone'`:
```powershell
cd D:\Class\movie-rcm-system\frontend
npm run build

# Sao chép static assets vào thư mục standalone (nếu triển khai container/server)
Copy-Item -Recurse -Force .next\static .next\standalone\.next\static
Copy-Item -Recurse -Force public .next\standalone\public

# Khởi động Node standalone server
node .next\standalone\server.js
```

### 5.3. Tắt tiến trình sạch sẽ (Graceful Shutdown)
Nhấn `Ctrl + C` trên terminal điều khiển.  
Để kiểm tra cổng không bị chiếm giữ:
```powershell
Get-NetTCPConnection -LocalPort 3000, 8080 -State Listen -ErrorAction SilentlyContinue
```

---

## 6. Kiểm Tra Khói & Xác Minh Hệ Thống (Smoke & Verification)

### 6.1. Kiểm tra Backend API
```bash
# Kiểm tra danh mục phim hoạt hình
curl -s "http://localhost:8080/api/movies?animationOnly=true&page=0&size=5" | jq .

# Kiểm tra chi tiết 1 phim canonical
curl -s "http://localhost:8080/api/movies/the-last-orbit" | jq .
```

### 6.2. Kiểm tra Frontend & Tests
```powershell
# 1. Typecheck
cd D:\Class\movie-rcm-system\frontend
npx tsc --noEmit

# 2. Toàn bộ 54+ tests kiểm thử hành vi người dùng, resilience, catalog
node --test (Get-ChildItem tests\*.mjs).FullName

# 3. Kiểm tra baseline catalog hoạt hình
node ..\scripts\preview_animation_catalog.cjs --test

# 4. Kiểm tra Spring Boot Unit & Integration tests (bao gồm chính sách seed)
cd ..\backend\springboot
$env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"
.\mvnw.cmd test -Dspring.profiles.active=test
```

---

## 7. Giới Hạn & Ranh Giới Kỹ Thuật (Boundaries & Constraints)

1. **AI / Chatbot Service:** Hiện tại CineBot kết nối qua mock route `/api/chat`. Khi cắm model Python / FastAPI / Qwen thực tế, cần duy trì đúng contract JSON và không chặn render UI.
2. **Image Host Whitelist:** Next.js Image chỉ nhận ảnh từ host cấu hình tại `next.config.ts` (`images.unsplash.com`). Ảnh lỗi hoặc từ host ngoài sẽ tự động chuyển sang poster placeholder fallback mà không gây sập layout.
3. **Data Isolation:** Khi chuyển đổi giữa các tài khoản (User A -> Logout -> User B), bộ nhớ đệm thư viện trong `WatchlistContext` bị hủy hoàn toàn ngay trong cùng render cycle (F1/F2 protection), đảm bảo không rò rỉ dữ liệu giữa người dùng.
