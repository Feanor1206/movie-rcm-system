package com.dippie.moviercm;

import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.repository.MovieRatingRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.repository.WatchlistItemRepository;
import com.dippie.moviercm.repository.FavoriteItemRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class CatalogIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private MovieRepository movieRepository;

    @Autowired
    private WatchlistItemRepository watchlistRepository;

    @Autowired
    private FavoriteItemRepository favoriteRepository;

    @Autowired
    private MovieRatingRepository ratingRepository;

    @BeforeEach
    void setupFixtures() {
        favoriteRepository.deleteAll();
        watchlistRepository.deleteAll();
        ratingRepository.deleteAll();
        movieRepository.deleteAll();

        saveMovie("spirited-away", "Spirited Away", 2001, 8.6, "Animation,Adventure,Family,Fantasy",
                "A young girl wanders into a magical bathhouse ruled by spirits and witches.");
        saveMovie("your-name", "Your Name", 2016, 8.4, "Animation, Romance, Drama, Fantasy",
                "Two teenagers share a magical connection swapping bodies across time and space.");
        saveMovie("isle-of-dogs", "Isle of Dogs", 2018, 7.8, "Animation,Adventure,Comedy,Drama",
                "A boy embarks on a stop-motion quest to rescue his exiled dog.");

        saveMovie("the-last-orbit", "The Last Orbit", 2026, 8.7, "Sci-Fi,Drama",
                "A lone astronaut discovers the signal guiding her home is the final memory.");
        saveMovie("afterlight", "Afterlight", 2025, 8.3, "Drama,Mystery",
                "In a city where night never ends, a photographer follows a beam of light.");

        saveMovie("melodrama-tears", "Melodrama Tears", 2022, 7.5, "Melodrama, Romance",
                "A tearjerker romance tale set across historical time.");
        saveMovie("non-animation-stunt", "NonAnimation Stunt", 2023, 7.0, "NonAnimation, Action",
                "A live-action stunt spectacular with no animated scenes.");

        saveMovie("wildcard-100", "Mission 100% Win", 2021, 8.4, "Action, Thriller",
                "Secret agent achieves victory with 100% precision.");

        saveMovie("bare-movie", "Bare Movie", 2015, 6.0, null, null);

        saveMovie("whitespace-chaos", "Whitespace Chaos", 2024, 7.9, "  Animation,   Family  ",
                "A movie with repeated spaces around commas and outer spaces.");
        saveMovie("tab-separated", "Tab Separated", 2024, 7.7, "\tAnimation\t,\tAdventure\t",
                "A movie with tabs surrounding tokens and commas.");
        saveMovie("multi-word-genre", "Galactic Quest", 2023, 8.1, "Sci-Fi & Fantasy, Martial Arts",
                "Epic space fantasy with martial arts combat.");
    }

    private void saveMovie(String id, String title, int year, double rating, String genres, String description) {
        movieRepository.save(Movie.builder()
                .id(id)
                .title(title)
                .year(year)
                .rating(rating)
                .runtime("2h")
                .genres(genres)
                .description(description)
                .poster("https://img.test/" + id + ".jpg")
                .backdrop("https://img.test/" + id + "-bg.jpg")
                .videoUrl(null)
                .build());
    }

    @Test
    @DisplayName("1. R2: Legacy search finds query in title OR description consistently and narrowing holds")
    void testR2SearchConsistency() throws Exception {
        mockMvc.perform(get("/api/movies")
                        .param("search", "time")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data", hasSize(2)))
                .andExpect(jsonPath("$.data[*].id", containsInAnyOrder("your-name", "melodrama-tears")));

        mockMvc.perform(get("/api/movies")
                        .param("search", "time")
                        .param("genre", "Animation")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].id").value("your-name"));

        mockMvc.perform(get("/api/movies/browse")
                        .param("query", "time")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.totalElements").value(2))
                .andExpect(jsonPath("$.data.items[*].id", containsInAnyOrder("your-name", "melodrama-tears")));
    }

    @Test
    @DisplayName("2. R1: Genre token exact matching rejects near-match substrings (Melodrama vs Drama)")
    void testR1GenreTokenExactMatching() throws Exception {
        mockMvc.perform(get("/api/movies")
                        .param("genre", "Drama")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data", hasSize(4)))
                .andExpect(jsonPath("$.data[*].id", containsInAnyOrder("your-name", "isle-of-dogs", "the-last-orbit", "afterlight")))
                .andExpect(jsonPath("$.data[*].id", not(hasItem("melodrama-tears"))));

        mockMvc.perform(get("/api/movies")
                        .param("genre", "Melodrama")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].id").value("melodrama-tears"));

        mockMvc.perform(get("/api/movies/browse")
                        .param("genre", "Animation")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.totalElements").value(5))
                .andExpect(jsonPath("$.data.items[*].id", containsInAnyOrder("spirited-away", "your-name", "isle-of-dogs", "whitespace-chaos", "tab-separated")))
                .andExpect(jsonPath("$.data.items[*].id", not(hasItem("non-animation-stunt"))));

        mockMvc.perform(get("/api/movies/browse")
                        .param("animationOnly", "true")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.totalElements").value(5))
                .andExpect(jsonPath("$.data.items[*].id", containsInAnyOrder("spirited-away", "your-name", "isle-of-dogs", "whitespace-chaos", "tab-separated")))
                .andExpect(jsonPath("$.data.items[*].id", not(hasItem("non-animation-stunt"))));
    }

    @Test
    @DisplayName("3. R1: Wildcards (%) in search queries are matched literally, not expanded")
    void testR1LiteralWildcardSearch() throws Exception {
        mockMvc.perform(get("/api/movies")
                        .param("search", "100%")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].id").value("wildcard-100"));

        mockMvc.perform(get("/api/movies")
                        .param("search", "10%")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(0)));
    }

    @Test
    @DisplayName("4. R1 & C3: Multi-genre AND filter matches only movies containing all requested tokens (including tabs)")
    void testR1MultiGenreAndFilter() throws Exception {
        mockMvc.perform(get("/api/movies/browse")
                        .param("genres", "Animation,Adventure")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.totalElements").value(3))
                .andExpect(jsonPath("$.data.items[*].id", containsInAnyOrder("spirited-away", "isle-of-dogs", "tab-separated")))
                .andExpect(jsonPath("$.data.items[*].id", not(hasItem("your-name"))));
    }

    @Test
    @DisplayName("5. Safe handling of nullable fields (null description, null genres)")
    void testNullFieldSafety() throws Exception {
        mockMvc.perform(get("/api/movies")
                        .param("search", "Bare Movie")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].id").value("bare-movie"));

        mockMvc.perform(get("/api/movies")
                        .param("genre", "Animation")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[*].id", not(hasItem("bare-movie"))));
    }

    @Test
    @DisplayName("6. /api/movies/browse paginates stably with tie-breaker id ASC across equal ratings")
    void testBrowsePaginationAndEqualSortTieBreak() throws Exception {
        mockMvc.perform(get("/api/movies/browse")
                        .param("page", "0")
                        .param("size", "4")
                        .param("sort", "rating")
                        .param("direction", "desc")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.items", hasSize(4)))
                .andExpect(jsonPath("$.data.items[0].id").value("the-last-orbit"))
                .andExpect(jsonPath("$.data.items[1].id").value("spirited-away"))
                .andExpect(jsonPath("$.data.items[2].id").value("wildcard-100"))
                .andExpect(jsonPath("$.data.items[3].id").value("your-name"));
    }

    @Test
    @DisplayName("7. /api/movies/browse rejects invalid parameters with 400 Bad Request")
    void testBrowseValidation() throws Exception {
        mockMvc.perform(get("/api/movies/browse").param("page", "-1"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));

        mockMvc.perform(get("/api/movies/browse").param("size", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));

        mockMvc.perform(get("/api/movies/browse").param("size", "101"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));

        mockMvc.perform(get("/api/movies/browse")
                        .param("yearMin", "2025")
                        .param("yearMax", "2010"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));

        mockMvc.perform(get("/api/movies/browse").param("sort", "unapproved_field"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));

        mockMvc.perform(get("/api/movies/browse").param("direction", "diagonal"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));
    }

    @Test
    @DisplayName("8. Detail endpoint returns 200 OK with trimmed genres, and 404 for nonexistent ID")
    void testMovieDetail() throws Exception {
        mockMvc.perform(get("/api/movies/spirited-away"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.id").value("spirited-away"))
                .andExpect(jsonPath("$.data.genres[0]").value("Animation"))
                .andExpect(jsonPath("$.data.genres[1]").value("Adventure"));

        mockMvc.perform(get("/api/movies/unknown-phantom-movie"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("Không tìm thấy phim."));
    }

    @Test
    @DisplayName("9. C3: Genre whitespace normalization (repeated spaces, tabs) and multi-word token exact match")
    void testC3GenreWhitespaceNormalizationAndMultiWordTokens() throws Exception {
        mockMvc.perform(get("/api/movies/browse")
                        .param("genre", "Family")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.totalElements").value(2))
                .andExpect(jsonPath("$.data.items[*].id", containsInAnyOrder("spirited-away", "whitespace-chaos")));

        mockMvc.perform(get("/api/movies/browse")
                        .param("genre", "Sci-Fi & Fantasy")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.totalElements").value(1))
                .andExpect(jsonPath("$.data.items[0].id").value("multi-word-genre"));

        mockMvc.perform(get("/api/movies/browse")
                        .param("genre", "Martial Arts")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.totalElements").value(1))
                .andExpect(jsonPath("$.data.items[0].id").value("multi-word-genre"));

        mockMvc.perform(get("/api/movies/browse")
                        .param("genre", "Adventure")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.totalElements").value(3))
                .andExpect(jsonPath("$.data.items[*].id", containsInAnyOrder("spirited-away", "isle-of-dogs", "tab-separated")));
    }
}


