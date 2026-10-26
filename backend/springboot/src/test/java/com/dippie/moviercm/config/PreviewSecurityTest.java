package com.dippie.moviercm.config;

import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.env.MockEnvironment;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import java.util.stream.Stream;

import static org.hamcrest.Matchers.containsString;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.head;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class PreviewSecurityTest {

    private static final String DB_NAME = "preview_security_" + UUID.randomUUID().toString().replace("-", "");
    private static final String ASSET_ID = "preview-security-public-asset";
    private static final byte[] MEDIA_BYTES = "public preview media bytes".getBytes(java.nio.charset.StandardCharsets.UTF_8);
    private static final Path MEDIA_ROOT = createMediaRoot();

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private MovieRepository movieRepository;

    @Autowired
    private MediaAssetRepository mediaAssetRepository;

    @DynamicPropertySource
    static void configureIsolatedPreviewContext(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:" + DB_NAME + ";DB_CLOSE_DELAY=-1;MODE=PostgreSQL;NON_KEYWORDS=YEAR,USER");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("app.media.root", () -> MEDIA_ROOT.toString());
        registry.add("app.catalog.snapshot-path", () -> MEDIA_ROOT.resolve("catalog-snapshot.json").toString());
        registry.add("app.cors.allowed-origins", () -> "http://localhost:3000,http://127.0.0.1:3000");
        registry.add("app.security.h2-console.enabled", () -> "false");
    }

    @BeforeEach
    void createPublicMediaFixture() throws IOException {
        mediaAssetRepository.deleteAll();
        movieRepository.deleteAll();
        movieRepository.save(Movie.builder()
                .id("preview-security-movie")
                .title("Preview Security Fixture")
                .year(2026)
                .rating(8.0)
                .runtime("1h")
                .genres("Animation")
                .description("Isolated security test fixture")
                .build());
        Files.write(MEDIA_ROOT.resolve("public-preview.mp4"), MEDIA_BYTES);
        mediaAssetRepository.save(new MediaAsset(
                ASSET_ID,
                "preview-security-movie",
                "feature",
                "local",
                "public-preview.mp4",
                "v1",
                "video/mp4",
                (long) MEDIA_BYTES.length,
                1.0,
                true,
                true
        ));
    }

    @AfterAll
    static void deleteTemporaryMedia() throws IOException {
        try (Stream<Path> paths = Files.walk(MEDIA_ROOT)) {
            for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) {
                Files.deleteIfExists(path);
            }
        }
    }

    @Test
    void allowedPreflightUsesAnExplicitCredentialedOriginAndAllowsRange() throws Exception {
        mockMvc.perform(options("/api/media/stream/" + ASSET_ID)
                        .header(HttpHeaders.ORIGIN, "http://localhost:3000")
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, "range"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "http://localhost:3000"))
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_CREDENTIALS, "true"))
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_HEADERS, containsString("range")));
    }

    @Test
    void disallowedPreflightDoesNotReceiveCorsPermission() throws Exception {
        mockMvc.perform(options("/api/media/stream/" + ASSET_ID)
                        .header(HttpHeaders.ORIGIN, "https://attacker.example")
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, "range"))
                .andExpect(status().isForbidden())
                .andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN));
    }

    @Test
    void publicAndAdminCatalogRequestsUseTheConfiguredCorsAllowlist() throws Exception {
        mockMvc.perform(get("/api/catalog/series")
                        .header(HttpHeaders.ORIGIN, "http://localhost:3000"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "http://localhost:3000"));

        mockMvc.perform(get("/api/admin/catalog/snapshots")
                        .header(HttpHeaders.ORIGIN, "http://localhost:3000"))
                .andExpect(status().isUnauthorized())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "http://localhost:3000"));
    }

    @Test
    void publicPlaybackKeepsAnonymousRangeAndHeadSupportWithFrameProtection() throws Exception {
        mockMvc.perform(head("/api/media/stream/" + ASSET_ID))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCEPT_RANGES, "bytes"))
                .andExpect(header().string(HttpHeaders.CONTENT_LENGTH, Long.toString(MEDIA_BYTES.length)))
                .andExpect(header().string("X-Frame-Options", "DENY"));

        mockMvc.perform(get("/api/media/stream/" + ASSET_ID)
                        .header(HttpHeaders.RANGE, "bytes=1-4"))
                .andExpect(status().isPartialContent())
                .andExpect(header().string(HttpHeaders.CONTENT_RANGE, "bytes 1-4/" + MEDIA_BYTES.length))
                .andExpect(content().bytes(new byte[]{MEDIA_BYTES[1], MEDIA_BYTES[2], MEDIA_BYTES[3], MEDIA_BYTES[4]}));
    }

    @Test
    void h2ConsoleRequiresAnExplicitDevOrTestOptIn() throws Exception {
        mockMvc.perform(get("/h2-console/"))
                .andExpect(status().isForbidden())
                .andExpect(header().string("X-Frame-Options", "DENY"));

        MockEnvironment dev = new MockEnvironment();
        dev.setActiveProfiles("dev");
        dev.withProperty("app.security.h2-console.enabled", "true");
        dev.withProperty("spring.h2.console.enabled", "true");
        assertTrue(SecurityConfig.isH2ConsoleExposureEnabled(dev));

        MockEnvironment mixed = new MockEnvironment();
        mixed.setActiveProfiles("prod", "dev");
        mixed.withProperty("app.security.h2-console.enabled", "true");
        mixed.withProperty("spring.h2.console.enabled", "true");
        assertFalse(SecurityConfig.isH2ConsoleExposureEnabled(mixed));

        MockEnvironment prod = new MockEnvironment();
        prod.setActiveProfiles("prod");
        prod.withProperty("app.security.h2-console.enabled", "true");
        prod.withProperty("spring.h2.console.enabled", "true");
        assertFalse(SecurityConfig.isH2ConsoleExposureEnabled(prod));
    }

    @Test
    void credentialedCorsRejectsWildcardOrigins() {
        assertEquals(List.of("https://preview.example", "http://localhost:3000"),
                SecurityConfig.parseAllowedOrigins("https://preview.example, http://localhost:3000"));
        assertThrows(IllegalStateException.class, () -> SecurityConfig.parseAllowedOrigins("https://preview.example,*"));
        assertThrows(IllegalStateException.class, () -> SecurityConfig.parseAllowedOrigins(" "));
    }

    private static Path createMediaRoot() {
        try {
            return Files.createTempDirectory("preview-security-media-");
        } catch (IOException e) {
            throw new ExceptionInInitializerError(e);
        }
    }
}
