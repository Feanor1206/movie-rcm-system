package com.dippie.moviercm.config;

import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.entity.MovieRating;
import com.dippie.moviercm.entity.Role;
import com.dippie.moviercm.entity.User;
import com.dippie.moviercm.entity.WatchlistItem;
import com.dippie.moviercm.repository.MovieRatingRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.repository.UserRepository;
import com.dippie.moviercm.repository.WatchlistItemRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
@ConditionalOnProperty(prefix = "app.seed", name = "enabled", havingValue = "true", matchIfMissing = false)
public class DataInitializer implements CommandLineRunner {

    private static final Logger logger = LoggerFactory.getLogger(DataInitializer.class);

    private final MovieRepository movieRepository;
    private final UserRepository userRepository;
    private final WatchlistItemRepository watchlistRepository;
    private final MovieRatingRepository ratingRepository;
    private final com.dippie.moviercm.repository.MediaAssetRepository mediaAssetRepository;
    private final PasswordEncoder passwordEncoder;

    public DataInitializer(MovieRepository movieRepository,
                           UserRepository userRepository,
                           WatchlistItemRepository watchlistRepository,
                           MovieRatingRepository ratingRepository,
                           com.dippie.moviercm.repository.MediaAssetRepository mediaAssetRepository,
                           PasswordEncoder passwordEncoder) {
        this.movieRepository = movieRepository;
        this.userRepository = userRepository;
        this.watchlistRepository = watchlistRepository;
        this.ratingRepository = ratingRepository;
        this.mediaAssetRepository = mediaAssetRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(String... args) {
        seedMovies();
        seed50Users();
        seedMediaAssets();
    }

    private void seedMovies() {
        logger.info("Kiểm tra và đồng bộ kho phim hoạt hình và phim Google Drive...");

        List<Movie> seedMovies = List.of(
                Movie.builder()
                        .id("drive-videoplayback")
                        .title("Shin Cậu Bé Bút Chì: Chuyến phiêu lưu kỳ thú")
                        .year(2026)
                        .rating(8.8)
                        .runtime("7m 25s")
                        .genres("Animation,Comedy,Adventure,Family")
                        .description("Tập phim Shin Cậu Bé Bút Chì phát từ Google Drive.")
                        .poster("https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/api/media/stream/ast-drive-videoplayback")
                        .build(),
                Movie.builder()
                        .id("the-last-orbit")
                        .title("The Last Orbit")
                        .year(2026)
                        .rating(8.7)
                        .runtime("2h 14m")
                        .genres("Animation,Sci-Fi,Drama")
                        .description("Một nữ phi hành gia lần theo tín hiệu dẫn cô về nhà. Đó có thể là ký ức cuối cùng của một thế giới đã mất.")
                        .poster("https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/videos/the-last-orbit.mp4")
                        .build(),
                Movie.builder()
                        .id("spirited-away")
                        .title("Spirited Away")
                        .year(2001)
                        .rating(8.6)
                        .runtime("2h 05m")
                        .genres("Animation,Adventure,Family,Fantasy")
                        .description("Một cô bé lạc vào nhà tắm của các linh hồn và phù thủy. Cô phải tìm cách cứu cha mẹ.")
                        .poster("https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/videos/the-last-orbit.mp4")
                        .build(),
                Movie.builder()
                        .id("your-name")
                        .title("Your Name")
                        .year(2016)
                        .rating(8.4)
                        .runtime("1h 46m")
                        .genres("Animation,Romance,Drama,Fantasy")
                        .description("Hai thiếu niên phát hiện họ có thể hoán đổi thân xác dù sống ở những nơi và thời điểm khác nhau.")
                        .poster("https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/videos/afterlight.mp4")
                        .build(),
                Movie.builder()
                        .id("spider-verse")
                        .title("Spider-Man: Into the Spider-Verse")
                        .year(2018)
                        .rating(8.4)
                        .runtime("1h 57m")
                        .genres("Animation,Action,Adventure,Sci-Fi")
                        .description("Miles Morales trở thành Người Nhện và gặp năm Người Nhện đến từ các chiều không gian khác.")
                        .poster("https://images.unsplash.com/photo-1635805737707-575885ab0820?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1635805737707-575885ab0820?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/videos/glass-horizon.mp4")
                        .build(),
                Movie.builder()
                        .id("isle-of-dogs")
                        .title("Isle of Dogs")
                        .year(2018)
                        .rating(7.8)
                        .runtime("1h 41m")
                        .genres("Animation,Adventure,Comedy,Drama")
                        .description("Một cậu bé ở Nhật Bản đến đảo rác để tìm Spots, chú chó bị đày khỏi thành phố.")
                        .poster("https://images.unsplash.com/photo-1548199973-03cce0bbc87b?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1548199973-03cce0bbc87b?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/videos/deep-blue.mp4")
                        .build(),
                Movie.builder()
                        .id("coraline")
                        .title("Coraline")
                        .year(2009)
                        .rating(7.7)
                        .runtime("1h 40m")
                        .genres("Animation,Drama,Family,Fantasy,Horror")
                        .description("Coraline, 11 tuổi, tìm thấy một thế giới giống nhà mình đến kỳ lạ. Nơi tưởng chừng hoàn hảo ấy che giấu những bí mật đáng sợ.")
                        .poster("https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/videos/nocturne.mp4")
                        .build(),
                Movie.builder()
                        .id("fantasia-1940")
                        .title("Fantasia")
                        .year(1940)
                        .rating(7.7)
                        .runtime("2h 05m")
                        .genres("Animation,Family,Fantasy,Musical")
                        .description("Tuyển tập hoạt hình lấy cảm hứng từ các tác phẩm nhạc cổ điển phương Tây.")
                        .poster("https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/videos/quiet-places.mp4")
                        .build(),
                Movie.builder()
                        .id("afterlight")
                        .title("Afterlight")
                        .year(2025)
                        .rating(8.3)
                        .runtime("1h 58m")
                        .genres("Animation,Drama,Mystery")
                        .description("Trong thành phố chìm trong đêm, một nhiếp ảnh gia lần theo tia nắng duy nhất.")
                        .poster("https://images.unsplash.com/photo-1519608487953-e999c86e7453?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1519608487953-e999c86e7453?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/videos/afterlight.mp4")
                        .build(),
                Movie.builder()
                        .id("glass-horizon")
                        .title("Glass Horizon")
                        .year(2026)
                        .rating(8.1)
                        .runtime("2h 06m")
                        .genres("Animation,Thriller,Sci-Fi")
                        .description("Một kiến trúc sư được giao thiết kế một thành phố mà cư dân không thể rời đi.")
                        .poster("https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/videos/glass-horizon.mp4")
                        .build(),
                Movie.builder()
                        .id("deep-blue")
                        .title("Deep Blue")
                        .year(2024)
                        .rating(7.9)
                        .runtime("1h 46m")
                        .genres("Animation,Adventure,Drama")
                        .description("Hai chị em xa cách cùng vượt qua vùng biển chưa có trên bản đồ để tìm cha.")
                        .poster("https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/videos/deep-blue.mp4")
                        .build(),
                Movie.builder()
                        .id("quiet-places")
                        .title("Quiet Places")
                        .year(2025)
                        .rating(8.5)
                        .runtime("2h 01m")
                        .genres("Animation,Romance,Drama")
                        .description("Một nữ nhạc sĩ trở về thị trấn từng bỏ đi và tìm lại một ca khúc cũ.")
                        .poster("https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/videos/quiet-places.mp4")
                        .build(),
                Movie.builder()
                        .id("nocturne")
                        .title("Nocturne")
                        .year(2024)
                        .rating(7.8)
                        .runtime("1h 52m")
                        .genres("Animation,Crime,Thriller")
                        .description("Một thám tử điều tra chuỗi vụ án xảy ra đúng nửa đêm.")
                        .poster("https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=600&q=85")
                        .backdrop("https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=1800&q=85")
                        .videoUrl("/videos/nocturne.mp4")
                        .build()
        );

        List<Movie> toSave = new ArrayList<>();
        for (Movie m : seedMovies) {
            if (!movieRepository.existsById(m.getId())) {
                toSave.add(m);
            }
        }
        if (!toSave.isEmpty()) {
            movieRepository.saveAll(toSave);
        }
        logger.info("Đã đồng bộ kho phim. Thêm mới {} phim.", toSave.size());
    }

    private void seed50Users() {
        if (!userRepository.existsByUsername("admin")) {
            userRepository.save(User.builder()
                    .username("admin")
                    .email("admin@dippie.com")
                    .fullName("System Administrator")
                    .password(passwordEncoder.encode("password123"))
                    .role(Role.ROLE_ADMIN)
                    .build());
            logger.info("[DataInitializer] Đã khởi tạo tài khoản quản trị mặc định: admin / password123 (ROLE_ADMIN)");
        }
        if (!userRepository.existsByUsername("user")) {
            userRepository.save(User.builder()
                    .username("user")
                    .email("user@dippie.com")
                    .fullName("Standard User")
                    .password(passwordEncoder.encode("password123"))
                    .role(Role.ROLE_USER)
                    .build());
            logger.info("[DataInitializer] Đã khởi tạo tài khoản người dùng mặc định: user / password123 (ROLE_USER)");
        }
        if (userRepository.count() < 10) {
            logger.info("Đang tự động nạp 50 tài khoản người dùng và dữ liệu tương tác mẫu...");
            String defaultPassword = passwordEncoder.encode("password123");

            String[][] usersData = {
                    {"admin", "admin@dippie.com", "System Admin", "ROLE_ADMIN"},
                    {"alex", "alex@dippie.com", "Alex Morgan", "ROLE_ADMIN"},
                    {"user", "user@dippie.com", "Standard User", "ROLE_USER"},
                    {"linh_dan", "linhdan@gmail.com", "Nguyễn Linh Đan", "ROLE_USER"},
                    {"minh_tri", "minhtri.tran@gmail.com", "Trần Minh Trí", "ROLE_USER"},
                    {"duc_anh", "ducanh.le@yahoo.com", "Lê Đức Anh", "ROLE_USER"},
                    {"mai_anh", "maianh.pham@outlook.com", "Phạm Mai Anh", "ROLE_USER"},
                    {"hoang_long", "hoanglong99@gmail.com", "Hoàng Long", "ROLE_USER"},
                    {"viet_dung", "dung.vu@gmail.com", "Vũ Việt Dũng", "ROLE_USER"},
                    {"huong_giang", "giang.dang@gmail.com", "Đặng Hương Giang", "ROLE_USER"},
                    {"tuan_kiet", "kiet.bui@gmail.com", "Bùi Tuấn Kiệt", "ROLE_USER"},
                    {"thao_vy", "thaovy.vo@gmail.com", "Võ Thảo Vy", "ROLE_USER"},
                    {"quang_huy", "huy.quang@gmail.com", "Đỗ Quang Huy", "ROLE_USER"},
                    {"ngoc_huyen", "huyen.ngoc@gmail.com", "Nguyễn Ngọc Huyền", "ROLE_USER"},
                    {"gia_bao", "giabao.le@gmail.com", "Lê Gia Bảo", "ROLE_USER"},
                    {"phuong_thao", "thao.phuong@gmail.com", "Trần Phương Thảo", "ROLE_USER"},
                    {"thanh_tung", "tung.thanh@gmail.com", "Phan Thanh Tùng", "ROLE_USER"},
                    {"ha_my", "hamy.vu@gmail.com", "Vũ Hà My", "ROLE_USER"},
                    {"nhat_minh", "minh.nhat@gmail.com", "Đặng Nhật Minh", "ROLE_USER"},
                    {"thu_trang", "trang.thu@gmail.com", "Nguyễn Thu Trang", "ROLE_USER"},
                    {"bao_nam", "nam.bao@gmail.com", "Trịnh Bảo Nam", "ROLE_USER"},
                    {"khanh_ly", "ly.khanh@gmail.com", "Bùi Khánh Ly", "ROLE_USER"},
                    {"david_kim", "david.kim@gmail.com", "David Kim", "ROLE_USER"},
                    {"elena_rostova", "elena.rostova@gmail.com", "Elena Rostova", "ROLE_USER"},
                    {"marcus_vance", "marcus.v@gmail.com", "Marcus Vance", "ROLE_USER"},
                    {"sarah_jenkins", "sarah.j@gmail.com", "Sarah Jenkins", "ROLE_USER"},
                    {"kenji_sato", "kenji.sato@gmail.com", "Kenji Sato", "ROLE_USER"},
                    {"lucas_silva", "lucas.silva@gmail.com", "Lucas Silva", "ROLE_USER"},
                    {"chloe_dupont", "chloe.dupont@gmail.com", "Chloe Dupont", "ROLE_USER"},
                    {"liam_miller", "liam.miller@gmail.com", "Liam Miller", "ROLE_USER"},
                    {"sophia_chen", "sophia.chen@gmail.com", "Sophia Chen", "ROLE_USER"},
                    {"noah_becker", "noah.becker@gmail.com", "Noah Becker", "ROLE_USER"},
                    {"tien_dat", "dat.tien@gmail.com", "Đoàn Tiến Đạt", "ROLE_USER"},
                    {"my_linh", "linh.my@gmail.com", "Ngô Mỹ Linh", "ROLE_USER"},
                    {"thai_son", "son.thai@gmail.com", "Dương Thái Sơn", "ROLE_USER"},
                    {"quynh_nga", "nga.quynh@gmail.com", "Lý Quỳnh Nga", "ROLE_USER"},
                    {"trung_hieu", "hieu.trung@gmail.com", "Hồ Trung Hiếu", "ROLE_USER"},
                    {"thanh_truc", "truc.thanh@gmail.com", "Trịnh Thanh Trúc", "ROLE_USER"},
                    {"van_phong", "phong.van@gmail.com", "Lê Văn Phong", "ROLE_USER"},
                    {"kieu_anh", "anh.kieu@gmail.com", "Mai Kiều Anh", "ROLE_USER"},
                    {"quoc_bao", "bao.quoc@gmail.com", "Phan Quốc Bảo", "ROLE_USER"},
                    {"minh_nguyet", "nguyet.minh@gmail.com", "Đỗ Minh Nguyệt", "ROLE_USER"},
                    {"anh_tuan", "tuan.anh@gmail.com", "Vũ Anh Tuấn", "ROLE_USER"},
                    {"hong_nhung", "nhung.hong@gmail.com", "Nguyễn Hồng Nhung", "ROLE_USER"},
                    {"trong_nhan", "nhan.trong@gmail.com", "Lương Trọng Nhân", "ROLE_USER"},
                    {"bich_ngoc", "ngoc.bich@gmail.com", "Võ Bích Ngọc", "ROLE_USER"},
                    {"hai_dang", "dang.hai@gmail.com", "Trần Hải Đăng", "ROLE_USER"},
                    {"thuy_tien", "tien.thuy@gmail.com", "Nguyễn Thủy Tiên", "ROLE_USER"},
                    {"hoang_nam", "nam.hoang@gmail.com", "Phạm Hoàng Nam", "ROLE_USER"},
                    {"kim_oanh", "oanh.kim@gmail.com", "Lê Kim Oanh", "ROLE_USER"},
                    {"the_vinh", "vinh.the@gmail.com", "Hoàng Thế Vinh", "ROLE_USER"},
                    {"lan_huong", "huong.lan@gmail.com", "Trương Lan Hương", "ROLE_USER"}
            };

            List<User> userList = new ArrayList<>();
            for (String[] u : usersData) {
                if (!userRepository.existsByUsername(u[0])) {
                    userList.add(User.builder()
                            .username(u[0])
                            .email(u[1])
                            .fullName(u[2])
                            .password(defaultPassword)
                            .role(u[3].equals("ROLE_ADMIN") ? Role.ROLE_ADMIN : Role.ROLE_USER)
                            .build());
                }
            }

            List<User> savedUsers = userRepository.saveAll(userList);
            logger.info("Đã nạp thành công {} tài khoản người dùng.", savedUsers.size());

            if (watchlistRepository.count() == 0 && savedUsers.size() > 0) {
                List<WatchlistItem> watchlistItems = new ArrayList<>();
                List<MovieRating> ratings = new ArrayList<>();

                String[] movieIds = {"the-last-orbit", "afterlight", "glass-horizon", "deep-blue", "quiet-places", "nocturne"};

                for (int i = 0; i < savedUsers.size(); i++) {
                    User u = savedUsers.get(i);
                    String m1 = movieIds[i % movieIds.length];
                    String m2 = movieIds[(i + 2) % movieIds.length];

                    watchlistItems.add(WatchlistItem.builder().userId(u.getId()).movieId(m1).movieTitle(m1).build());
                    watchlistItems.add(WatchlistItem.builder().userId(u.getId()).movieId(m2).movieTitle(m2).build());

                    ratings.add(MovieRating.builder().userId(u.getId()).movieId(m1).rating(8 + (i % 3)).build());
                    ratings.add(MovieRating.builder().userId(u.getId()).movieId(m2).rating(7 + (i % 4)).build());
                }

                watchlistRepository.saveAll(watchlistItems);
                ratingRepository.saveAll(ratings);
                logger.info("Đã nạp {} mục Watchlist và {} đánh giá sao mẫu.", watchlistItems.size(), ratings.size());
            }
        }
    }

    private void seedMediaAssets() {
        if (!mediaAssetRepository.existsById("ast-drive-videoplayback")) {
            logger.info("Đang tự động nạp Media Asset cho Google Drive video (videoplayback.mp4)...");
            mediaAssetRepository.save(new com.dippie.moviercm.entity.MediaAsset(
                    "ast-drive-videoplayback",
                    "drive-videoplayback",
                    "feature",
                    "drive",
                    "videoplayback.mp4",
                    "v1",
                    "video/mp4",
                    29209556L,
                    445.8,
                    true,
                    true
            ));
        }

        List<com.dippie.moviercm.entity.MediaAsset> assets = List.of(
                new com.dippie.moviercm.entity.MediaAsset(
                        "ast-orbit-feat",
                        "the-last-orbit",
                        "feature",
                        "local",
                        "synthetic/feature_test.mp4",
                        "v1",
                        "video/mp4",
                        137961L,
                        10.0,
                        true,
                        true
                ),
                new com.dippie.moviercm.entity.MediaAsset(
                        "ast-orbit-trl",
                        "the-last-orbit",
                        "trailer",
                        "local",
                        "synthetic/trailer_test.mp4",
                        "v1",
                        "video/mp4",
                        45095L,
                        3.0,
                        true,
                        true
                ),
                new com.dippie.moviercm.entity.MediaAsset(
                        "ast-afterlight-trl",
                        "afterlight",
                        "trailer",
                        "local",
                        "synthetic/trailer_test.mp4",
                        "v1",
                        "video/mp4",
                        45095L,
                        3.0,
                        true,
                        true
                )
        );

        for (var a : assets) {
            if (!mediaAssetRepository.existsById(a.getId())) {
                mediaAssetRepository.save(a);
            }
        }
    }
}

