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
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
public class DataInitializer implements CommandLineRunner {

    private static final Logger logger = LoggerFactory.getLogger(DataInitializer.class);

    private final MovieRepository movieRepository;
    private final UserRepository userRepository;
    private final WatchlistItemRepository watchlistRepository;
    private final MovieRatingRepository ratingRepository;
    private final PasswordEncoder passwordEncoder;

    public DataInitializer(MovieRepository movieRepository,
                           UserRepository userRepository,
                           WatchlistItemRepository watchlistRepository,
                           MovieRatingRepository ratingRepository,
                           PasswordEncoder passwordEncoder) {
        this.movieRepository = movieRepository;
        this.userRepository = userRepository;
        this.watchlistRepository = watchlistRepository;
        this.ratingRepository = ratingRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(String... args) {
        seedMovies();
        seed50Users();
    }

    private void seedMovies() {
        if (movieRepository.count() == 0) {
            logger.info("Cơ sở dữ liệu phim trống. Đang tự động nạp 6 phim mẫu...");

            List<Movie> seedMovies = List.of(
                    Movie.builder()
                            .id("the-last-orbit")
                            .title("The Last Orbit")
                            .year(2026)
                            .rating(8.7)
                            .runtime("2h 14m")
                            .genres("Sci-Fi,Drama")
                            .description("A lone astronaut discovers that the signal guiding her home may be the final memory of a world already gone.")
                            .poster("https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=600&q=85")
                            .backdrop("https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=1800&q=85")
                            .videoUrl("/videos/the-last-orbit.mp4")
                            .build(),
                    Movie.builder()
                            .id("afterlight")
                            .title("Afterlight")
                            .year(2025)
                            .rating(8.3)
                            .runtime("1h 58m")
                            .genres("Drama,Mystery")
                            .description("In a city where night never ends, a photographer follows one impossible beam of sunlight.")
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
                            .genres("Thriller,Sci-Fi")
                            .description("A brilliant architect is asked to design a city that no one is meant to leave.")
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
                            .genres("Adventure,Drama")
                            .description("Two estranged sisters cross an unmapped ocean in search of their father.")
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
                            .genres("Romance,Drama")
                            .description("A composer returns to the town she fled and finds an old song waiting for her.")
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
                            .genres("Crime,Thriller")
                            .description("A detective investigates a string of elegant crimes committed at midnight.")
                            .poster("https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=600&q=85")
                            .backdrop("https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=1800&q=85")
                            .videoUrl("/videos/nocturne.mp4")
                            .build()
            );

            movieRepository.saveAll(seedMovies);
            logger.info("Đã nạp thành công {} phim vào cơ sở dữ liệu.", seedMovies.size());
        }
    }

    private void seed50Users() {
        if (userRepository.count() < 10) {
            logger.info("Đang tự động nạp 50 tài khoản người dùng và dữ liệu tương tác mẫu...");
            String defaultPassword = passwordEncoder.encode("password123");

            String[][] usersData = {
                    {"alex", "alex@dippie.com", "Alex Morgan", "ROLE_ADMIN"},
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
                userList.add(User.builder()
                        .username(u[0])
                        .email(u[1])
                        .fullName(u[2])
                        .password(defaultPassword)
                        .role(u[3].equals("ROLE_ADMIN") ? Role.ROLE_ADMIN : Role.ROLE_USER)
                        .build());
            }

            List<User> savedUsers = userRepository.saveAll(userList);
            logger.info("Đã nạp thành công {} tài khoản người dùng.", savedUsers.size());

            // Seed Sample Watchlists & Ratings
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
}
