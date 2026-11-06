package com.dippie.moviercm;

import com.dippie.moviercm.dto.*;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.repository.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

import static org.hamcrest.Matchers.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AuthAndLibraryIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private MovieRepository movieRepository;

    @Autowired
    private WatchlistItemRepository watchlistRepository;

    @Autowired
    private FavoriteItemRepository favoriteRepository;

    @Autowired
    private MovieRatingRepository ratingRepository;

    @BeforeEach
    void cleanDatabase() {
        favoriteRepository.deleteAll();
        watchlistRepository.deleteAll();
        ratingRepository.deleteAll();
        userRepository.deleteAll();

        // Seed canonical catalog movie fixtures (R5)
        seedCatalogMovie("the-last-orbit", "The Last Orbit", "https://img.jpg/the-last-orbit");
        seedCatalogMovie("afterlight", "Afterlight", "https://img.jpg/afterlight");
        seedCatalogMovie("glass-horizon", "Glass Horizon", "https://img.jpg/glass-horizon");
        seedCatalogMovie("deep-blue", "Deep Blue", "https://img.jpg/deep-blue");
    }

    private void seedCatalogMovie(String id, String title, String poster) {
        if (!movieRepository.existsById(id)) {
            movieRepository.save(Movie.builder()
                    .id(id)
                    .title(title)
                    .poster(poster)
                    .year(2025)
                    .genres("Sci-Fi,Drama")
                    .rating(8.5)
                    .runtime("2h")
                    .description("Seeded test fixture")
                    .build());
        }
    }

    private String registerAndGetToken(String username, String email, String password, String fullName) throws Exception {
        RegisterRequest registerReq = new RegisterRequest(username, email, password, fullName);
        MvcResult result = mockMvc.perform(post("/api/auth/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(registerReq)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.token").isNotEmpty())
                .andReturn();

        JsonNode root = objectMapper.readTree(result.getResponse().getContentAsString());
        return root.path("data").path("token").asText();
    }

    @Test
    @DisplayName("1. User registration preserves raw password with spaces and login succeeds")
    void testRegistrationAndLoginWithSpacesInPassword() throws Exception {
        String rawPassword = " my secret pass 123 ";
        RegisterRequest req = new RegisterRequest("testuser", "testuser@example.com", rawPassword, "Test User");

        mockMvc.perform(post("/api/auth/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.username").value("testuser"))
                .andExpect(jsonPath("$.data.password").doesNotExist()); // No password hash exposed

        // Login with exact raw password
        AuthRequest loginReq = new AuthRequest("testuser", rawPassword);
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(loginReq)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.token").isNotEmpty());

        // Login with trimmed password must fail
        AuthRequest badLoginReq = new AuthRequest("testuser", "my secret pass 123");
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(badLoginReq)))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("2. /api/auth/me requires valid token and returns authenticated principal")
    void testCurrentUserEndpoint() throws Exception {
        // Without token -> 401
        mockMvc.perform(get("/api/auth/me"))
                .andExpect(status().isUnauthorized());

        String token = registerAndGetToken("alice", "alice@example.com", "password123", "Alice Smith");

        // With valid token -> 200
        mockMvc.perform(get("/api/auth/me")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.username").value("alice"))
                .andExpect(jsonPath("$.data.email").value("alice@example.com"))
                .andExpect(jsonPath("$.data.fullName").value("Alice Smith"));
    }

    @Test
    @DisplayName("3. Watchlist operations: canonical metadata overrides forged client title, duplicate idempotency, list, and delete")
    void testWatchlistFlow() throws Exception {
        String token = registerAndGetToken("bob", "bob@example.com", "password123", "Bob Jones");

        // Initially empty
        mockMvc.perform(get("/api/users/watchlist")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(0)));

        // Add movie with forged client title and poster
        WatchlistRequest addReq = new WatchlistRequest("the-last-orbit", "Forged Fake Title", "https://forged.jpg");
        mockMvc.perform(post("/api/users/watchlist")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(addReq)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.movieId").value("the-last-orbit"))
                // Canonical catalog metadata must override forged client metadata (R5)
                .andExpect(jsonPath("$.data.movieTitle").value("The Last Orbit"))
                .andExpect(jsonPath("$.data.posterUrl").value(movieRepository.findById("the-last-orbit").get().getPoster()));

        // Duplicate add is idempotent (no duplicate rows, 200 OK)
        mockMvc.perform(post("/api/users/watchlist")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(addReq)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.movieId").value("the-last-orbit"));

        mockMvc.perform(get("/api/users/watchlist")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)));

        // Delete movie
        mockMvc.perform(delete("/api/users/watchlist/the-last-orbit")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk());

        // Now empty
        mockMvc.perform(get("/api/users/watchlist")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(0)));
    }

    @Test
    @DisplayName("4. Favorites operations: add, duplicate idempotency, list, and delete")
    void testFavoritesFlow() throws Exception {
        String token = registerAndGetToken("carol", "carol@example.com", "password123", "Carol White");

        // Initially empty
        mockMvc.perform(get("/api/users/favorites")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(0)));

        // Add favorite
        FavoriteRequest favReq = new FavoriteRequest("afterlight", "Forged Afterlight", "https://forged.jpg");
        mockMvc.perform(post("/api/users/favorites")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(favReq)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.movieId").value("afterlight"))
                .andExpect(jsonPath("$.data.movieTitle").value("Afterlight")); // Canonical metadata

        // Duplicate add is idempotent
        mockMvc.perform(post("/api/users/favorites")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(favReq)))
                .andExpect(status().isOk());

        mockMvc.perform(get("/api/users/favorites")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)));

        // Delete favorite
        mockMvc.perform(delete("/api/users/favorites/afterlight")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk());

        mockMvc.perform(get("/api/users/favorites")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(0)));
    }

    @Test
    @DisplayName("5. Rating operations: add, update, validation boundary, and delete")
    void testRatingFlow() throws Exception {
        String token = registerAndGetToken("dan", "dan@example.com", "password123", "Dan Brown");

        // Add rating 8
        RatingRequest rateReq = new RatingRequest("glass-horizon", 8);
        mockMvc.perform(post("/api/users/ratings")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(rateReq)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.rating").value(8));

        // Update rating to 10 (same movie, single record)
        RatingRequest updateReq = new RatingRequest("glass-horizon", 10);
        mockMvc.perform(post("/api/users/ratings")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(updateReq)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.rating").value(10));

        // Total ratings is 1
        mockMvc.perform(get("/api/users/ratings")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].rating").value(10));

        // Boundary validation: rating 0 must fail with 400 Bad Request
        RatingRequest invalidLow = new RatingRequest("glass-horizon", 0);
        mockMvc.perform(post("/api/users/ratings")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(invalidLow)))
                .andExpect(status().isBadRequest());

        // Boundary validation: rating 11 must fail with 400 Bad Request
        RatingRequest invalidHigh = new RatingRequest("glass-horizon", 11);
        mockMvc.perform(post("/api/users/ratings")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(invalidHigh)))
                .andExpect(status().isBadRequest());

        // Delete rating
        mockMvc.perform(delete("/api/users/ratings/glass-horizon")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk());

        mockMvc.perform(get("/api/users/ratings")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(0)));
    }

    @Test
    @DisplayName("6. Actor isolation between User A and User B")
    void testActorIsolationBetweenUsers() throws Exception {
        String tokenA = registerAndGetToken("user_a", "usera@example.com", "password123", "User A");
        String tokenB = registerAndGetToken("user_b", "userb@example.com", "password123", "User B");

        // User A adds watchlist, favorite, rating using real catalog movies
        mockMvc.perform(post("/api/users/watchlist")
                        .header("Authorization", "Bearer " + tokenA)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new WatchlistRequest("the-last-orbit", "The Last Orbit", "img1"))))
                .andExpect(status().isOk());

        mockMvc.perform(post("/api/users/favorites")
                        .header("Authorization", "Bearer " + tokenA)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new FavoriteRequest("afterlight", "Afterlight", "img2"))))
                .andExpect(status().isOk());

        mockMvc.perform(post("/api/users/ratings")
                        .header("Authorization", "Bearer " + tokenA)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new RatingRequest("glass-horizon", 9))))
                .andExpect(status().isOk());

        // Verify User A has 1 item each
        mockMvc.perform(get("/api/users/watchlist").header("Authorization", "Bearer " + tokenA))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data", hasSize(1)));
        mockMvc.perform(get("/api/users/favorites").header("Authorization", "Bearer " + tokenA))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data", hasSize(1)));
        mockMvc.perform(get("/api/users/ratings").header("Authorization", "Bearer " + tokenA))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data", hasSize(1)));

        // User B must have ZERO items (total isolation)
        mockMvc.perform(get("/api/users/watchlist").header("Authorization", "Bearer " + tokenB))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data", hasSize(0)));
        mockMvc.perform(get("/api/users/favorites").header("Authorization", "Bearer " + tokenB))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data", hasSize(0)));
        mockMvc.perform(get("/api/users/ratings").header("Authorization", "Bearer " + tokenB))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data", hasSize(0)));
    }

    @Test
    @DisplayName("7. R5 Catalog Validation: non-existent movie IDs are rejected with 400 Bad Request; orphan deletion allowed")
    void testCatalogValidation() throws Exception {
        String token = registerAndGetToken("eva", "eva@example.com", "password123", "Eva Green");
        String badMovieId = "non-existent-movie-999";

        // Watchlist add non-existent -> 400 Bad Request with structured error
        mockMvc.perform(post("/api/users/watchlist")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new WatchlistRequest(badMovieId, "Fake", "fake.jpg"))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message", containsString("Phim không tồn tại trong danh mục")));

        // Favorites add non-existent -> 400 Bad Request
        mockMvc.perform(post("/api/users/favorites")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new FavoriteRequest(badMovieId, "Fake", "fake.jpg"))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message", containsString("Phim không tồn tại trong danh mục")));

        // Rating add non-existent -> 400 Bad Request
        mockMvc.perform(post("/api/users/ratings")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new RatingRequest(badMovieId, 7))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message", containsString("Phim không tồn tại trong danh mục")));

        // Legacy orphan deletion of non-catalog ID succeeds safely (200 OK)
        mockMvc.perform(delete("/api/users/watchlist/" + badMovieId)
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk());
        mockMvc.perform(delete("/api/users/favorites/" + badMovieId)
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk());
        mockMvc.perform(delete("/api/users/ratings/" + badMovieId)
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("8. R6 Concurrent Idempotency: simultaneous writes synchronized by CountDownLatch return 200 OK with single row")
    void testConcurrentIdempotency() throws Exception {
        String token = registerAndGetToken("frank", "frank@example.com", "password123", "Frank Miller");
        ExecutorService executor = Executors.newFixedThreadPool(4);

        try {
            // Concurrent Watchlist writes
            CountDownLatch barrier = new CountDownLatch(1);
            AtomicInteger okResponses = new AtomicInteger(0);

            Callable<Integer> addWatchlistTask = () -> {
                barrier.await();
                MvcResult res = mockMvc.perform(post("/api/users/watchlist")
                                .header("Authorization", "Bearer " + token)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(objectMapper.writeValueAsString(new WatchlistRequest("deep-blue", "Deep Blue", "poster"))))
                        .andReturn();
                if (res.getResponse().getStatus() == 200) {
                    okResponses.incrementAndGet();
                }
                return res.getResponse().getStatus();
            };

            Future<Integer> f1 = executor.submit(addWatchlistTask);
            Future<Integer> f2 = executor.submit(addWatchlistTask);
            barrier.countDown(); // Trigger simultaneous execution

            int status1 = f1.get(5, TimeUnit.SECONDS);
            int status2 = f2.get(5, TimeUnit.SECONDS);

            assertEquals(200, status1);
            assertEquals(200, status2);
            assertEquals(2, okResponses.get());

            // Exact count in DB must be 1
            mockMvc.perform(get("/api/users/watchlist").header("Authorization", "Bearer " + token))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.data", hasSize(1)));

            // Concurrent Favorites writes
            CountDownLatch favBarrier = new CountDownLatch(1);
            Callable<Integer> addFavTask = () -> {
                favBarrier.await();
                MvcResult res = mockMvc.perform(post("/api/users/favorites")
                                .header("Authorization", "Bearer " + token)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(objectMapper.writeValueAsString(new FavoriteRequest("deep-blue", "Deep Blue", "poster"))))
                        .andReturn();
                return res.getResponse().getStatus();
            };

            Future<Integer> ff1 = executor.submit(addFavTask);
            Future<Integer> ff2 = executor.submit(addFavTask);
            favBarrier.countDown();

            assertEquals(200, ff1.get(5, TimeUnit.SECONDS));
            assertEquals(200, ff2.get(5, TimeUnit.SECONDS));

            // Verify persisted row has valid non-null ID
            MvcResult favListRes = mockMvc.perform(get("/api/users/favorites").header("Authorization", "Bearer " + token))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.data", hasSize(1)))
                    .andExpect(jsonPath("$.data[0].id").isNumber())
                    .andReturn();
            JsonNode favData = objectMapper.readTree(favListRes.getResponse().getContentAsString()).path("data").get(0);
            assertTrue(favData.path("id").asLong() > 0, "Persisted favorite must have a valid positive ID");

            // Concurrent Rating writes
            CountDownLatch ratingBarrier = new CountDownLatch(1);
            Callable<Integer> addRatingTask1 = () -> {
                ratingBarrier.await();
                return mockMvc.perform(post("/api/users/ratings")
                                .header("Authorization", "Bearer " + token)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(objectMapper.writeValueAsString(new RatingRequest("deep-blue", 8))))
                        .andReturn().getResponse().getStatus();
            };
            Callable<Integer> addRatingTask2 = () -> {
                ratingBarrier.await();
                return mockMvc.perform(post("/api/users/ratings")
                                .header("Authorization", "Bearer " + token)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(objectMapper.writeValueAsString(new RatingRequest("deep-blue", 9))))
                        .andReturn().getResponse().getStatus();
            };

            Future<Integer> rf1 = executor.submit(addRatingTask1);
            Future<Integer> rf2 = executor.submit(addRatingTask2);
            ratingBarrier.countDown();

            assertEquals(200, rf1.get(5, TimeUnit.SECONDS));
            assertEquals(200, rf2.get(5, TimeUnit.SECONDS));

            // Final rating count in DB must be exactly 1 record with valid persisted ID
            MvcResult ratingListRes = mockMvc.perform(get("/api/users/ratings").header("Authorization", "Bearer " + token))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.data", hasSize(1)))
                    .andExpect(jsonPath("$.data[0].id").isNumber())
                    .andReturn();
            JsonNode ratingData = objectMapper.readTree(ratingListRes.getResponse().getContentAsString()).path("data").get(0);
            assertTrue(ratingData.path("id").asLong() > 0, "Persisted rating must have a valid positive ID");

        } finally {
            executor.shutdown();
        }
    }
}
