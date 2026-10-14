package com.dippie.moviercm;

import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.exception.MediaNotFoundException;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.service.DriveMediaStorageAdapter;
import com.dippie.moviercm.service.MediaStreamService;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Comparator;

import static org.hamcrest.Matchers.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.head;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Comprehensive integration tests for Google Drive mounted media storage (provider=drive).
 * Evaluates descriptor resolution, HEAD, full GET, HTTP 206 Range seeking,
 * 416 Range Not Satisfiable, 404 Not Found, 503 MediaUnavailableException on mount disconnect,
 * private asset isolation, and 429 concurrency limit permit management.
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class DriveMediaStreamingIntegrationTest {

    private static Path mockDriveMount;
    private static byte[] featureBytes;
    private static byte[] trailerBytes;

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private MovieRepository movieRepository;

    @Autowired
    private MediaAssetRepository mediaAssetRepository;

    @Autowired
    private DriveMediaStorageAdapter driveStorageAdapter;

    @Autowired
    private MediaStreamService mediaStreamService;

    @BeforeAll
    static void initMockDriveMount() throws IOException {
        mockDriveMount = Files.createTempDirectory("mock-gdrive-mount-");

        // Seed synthetic feature video bytes (10,000 bytes)
        featureBytes = new byte[10000];
        for (int i = 0; i < featureBytes.length; i++) {
            featureBytes[i] = (byte) ((i * 31 + 7) % 128);
        }

        // Seed synthetic trailer video bytes (5,000 bytes)
        trailerBytes = new byte[5000];
        for (int i = 0; i < trailerBytes.length; i++) {
            trailerBytes[i] = (byte) ((i * 17 + 13) % 128);
        }
    }

    @DynamicPropertySource
    static void registerDriveMountProperties(DynamicPropertyRegistry registry) {
        registry.add("app.media.drive-mount", () -> mockDriveMount.toAbsolutePath().toString());
    }

    @AfterAll
    static void cleanupMockDriveMount() throws IOException {
        if (mockDriveMount != null && Files.exists(mockDriveMount)) {
            try (var stream = Files.walk(mockDriveMount)) {
                stream.sorted(Comparator.reverseOrder())
                        .forEach(p -> {
                            try {
                                Files.deleteIfExists(p);
                            } catch (IOException ignored) {
                            }
                        });
            }
        }
    }

    @BeforeEach
    void setupFixtures() throws IOException {
        mediaAssetRepository.deleteAll();
        movieRepository.deleteAll();

        // Recreate directory structure inside mock drive mount if not present
        Path movieDir = mockDriveMount.resolve("movies/m4-drive-movie/v1");
        Files.createDirectories(movieDir);

        Path featureFile = movieDir.resolve("feature.mp4");
        Files.write(featureFile, featureBytes);

        Path trailerFile = movieDir.resolve("trailer.mp4");
        Files.write(trailerFile, trailerBytes);

        // 1. Movie configured with Drive assets
        Movie movie = Movie.builder()
                .id("m4-drive-movie")
                .title("Drive Animation Odyssey")
                .year(2026)
                .rating(9.3)
                .runtime("0h 25m")
                .genres("Animation,Sci-Fi")
                .description("Animation feature served from Google Drive Windows mount.")
                .poster("https://example.com/poster-drive.jpg")
                .backdrop("https://example.com/backdrop-drive.jpg")
                .videoUrl("/videos/fallback-drive.mp4")
                .build();
        movieRepository.save(movie);

        // 2. Public Feature asset (storageProvider = "drive")
        MediaAsset featureAsset = new MediaAsset(
                "ast-drive-feat-1",
                "m4-drive-movie",
                "feature",
                "drive",
                "movies/m4-drive-movie/v1/feature.mp4",
                "v1",
                "video/mp4",
                (long) featureBytes.length,
                25.0,
                true,
                true
        );
        mediaAssetRepository.save(featureAsset);

        // 3. Public Trailer asset (storageProvider = "drive")
        MediaAsset trailerAsset = new MediaAsset(
                "ast-drive-trl-1",
                "m4-drive-movie",
                "trailer",
                "drive",
                "movies/m4-drive-movie/v1/trailer.mp4",
                "v1",
                "video/mp4",
                (long) trailerBytes.length,
                5.0,
                true,
                true
        );
        mediaAssetRepository.save(trailerAsset);
    }

    @Test
    @DisplayName("Descriptor returns HTTP 200 with both Drive feature and trailer assets")
    void testDriveMediaDescriptor() throws Exception {
        mockMvc.perform(get("/api/movies/m4-drive-movie/media-descriptor"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.movieId", is("m4-drive-movie")))
                .andExpect(jsonPath("$.hasFeature", is(true)))
                .andExpect(jsonPath("$.hasTrailer", is(true)))
                .andExpect(jsonPath("$.feature.assetId", is("ast-drive-feat-1")))
                .andExpect(jsonPath("$.feature.kind", is("feature")))
                .andExpect(jsonPath("$.feature.streamUrl", is("/api/media/stream/ast-drive-feat-1")))
                .andExpect(jsonPath("$.feature.mimeType", is("video/mp4")))
                .andExpect(jsonPath("$.feature.byteLength", is(featureBytes.length)))
                .andExpect(jsonPath("$.trailer.assetId", is("ast-drive-trl-1")))
                .andExpect(jsonPath("$.trailer.streamUrl", is("/api/media/stream/ast-drive-trl-1")))
                .andExpect(jsonPath("$.trailer.byteLength", is(trailerBytes.length)));
    }

    @Test
    @DisplayName("HEAD request returns HTTP 200, Content-Type, Content-Length, Accept-Ranges: bytes, ETag and empty body")
    void testHeadDriveMediaStreamingHeaders() throws Exception {
        MvcResult result = mockMvc.perform(head("/api/media/stream/ast-drive-feat-1"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.CONTENT_TYPE, "video/mp4"))
                .andExpect(header().string(HttpHeaders.ACCEPT_RANGES, "bytes"))
                .andExpect(header().string(HttpHeaders.CONTENT_LENGTH, String.valueOf(featureBytes.length)))
                .andExpect(header().exists(HttpHeaders.ETAG))
                .andExpect(header().string(HttpHeaders.CACHE_CONTROL, containsString("public")))
                .andReturn();

        assertEquals(0, result.getResponse().getContentAsByteArray().length, "HEAD response body must be completely empty");
    }

    @Test
    @DisplayName("GET stream without Range returns HTTP 200 and entire Drive video payload")
    void testFullStreamWithoutRange() throws Exception {
        MvcResult result = mockMvc.perform(get("/api/media/stream/ast-drive-feat-1"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.CONTENT_TYPE, "video/mp4"))
                .andExpect(header().string(HttpHeaders.ACCEPT_RANGES, "bytes"))
                .andExpect(header().string(HttpHeaders.CONTENT_LENGTH, String.valueOf(featureBytes.length)))
                .andReturn();

        byte[] receivedBytes = result.getResponse().getContentAsByteArray();
        assertArrayEquals(featureBytes, receivedBytes, "Full stream content must match exact Drive file bytes");
    }

    @Test
    @DisplayName("GET stream with closed range at beginning (bytes=0-1023) returns HTTP 206 Partial Content")
    void testRangeBeginning() throws Exception {
        byte[] expected = Arrays.copyOfRange(featureBytes, 0, 1024);

        MvcResult result = mockMvc.perform(get("/api/media/stream/ast-drive-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=0-1023"))
                .andExpect(status().isPartialContent())
                .andExpect(header().string(HttpHeaders.ACCEPT_RANGES, "bytes"))
                .andExpect(header().string(HttpHeaders.CONTENT_RANGE, "bytes 0-1023/" + featureBytes.length))
                .andExpect(header().string(HttpHeaders.CONTENT_LENGTH, "1024"))
                .andReturn();

        byte[] actual = result.getResponse().getContentAsByteArray();
        assertArrayEquals(expected, actual, "Ranged bytes 0-1023 must match expected segment");
    }

    @Test
    @DisplayName("GET stream with closed range in middle (bytes=1000-2000) returns HTTP 206 Partial Content")
    void testRangeMiddle() throws Exception {
        byte[] expected = Arrays.copyOfRange(featureBytes, 1000, 2001);

        MvcResult result = mockMvc.perform(get("/api/media/stream/ast-drive-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=1000-2000"))
                .andExpect(status().isPartialContent())
                .andExpect(header().string(HttpHeaders.ACCEPT_RANGES, "bytes"))
                .andExpect(header().string(HttpHeaders.CONTENT_RANGE, "bytes 1000-2000/" + featureBytes.length))
                .andExpect(header().string(HttpHeaders.CONTENT_LENGTH, "1001"))
                .andReturn();

        byte[] actual = result.getResponse().getContentAsByteArray();
        assertArrayEquals(expected, actual, "Ranged bytes 1000-2000 must match expected segment");
    }

    @Test
    @DisplayName("GET stream with open-ended range (bytes=5000-) returns HTTP 206 Partial Content to end of file")
    void testRangeOpenEnded() throws Exception {
        byte[] expected = Arrays.copyOfRange(featureBytes, 5000, featureBytes.length);

        MvcResult result = mockMvc.perform(get("/api/media/stream/ast-drive-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=5000-"))
                .andExpect(status().isPartialContent())
                .andExpect(header().string(HttpHeaders.ACCEPT_RANGES, "bytes"))
                .andExpect(header().string(HttpHeaders.CONTENT_RANGE, "bytes 5000-9999/" + featureBytes.length))
                .andExpect(header().string(HttpHeaders.CONTENT_LENGTH, "5000"))
                .andReturn();

        byte[] actual = result.getResponse().getContentAsByteArray();
        assertArrayEquals(expected, actual, "Open-ended range 5000- must match final 5000 bytes");
    }

    @Test
    @DisplayName("GET stream with suffix range (bytes=-500) returns HTTP 206 Partial Content for last 500 bytes")
    void testRangeSuffix() throws Exception {
        int suffixLen = 500;
        int startPos = featureBytes.length - suffixLen;
        byte[] expected = Arrays.copyOfRange(featureBytes, startPos, featureBytes.length);

        MvcResult result = mockMvc.perform(get("/api/media/stream/ast-drive-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=-" + suffixLen))
                .andExpect(status().isPartialContent())
                .andExpect(header().string(HttpHeaders.ACCEPT_RANGES, "bytes"))
                .andExpect(header().string(HttpHeaders.CONTENT_RANGE, "bytes " + startPos + "-9999/" + featureBytes.length))
                .andExpect(header().string(HttpHeaders.CONTENT_LENGTH, String.valueOf(suffixLen)))
                .andReturn();

        byte[] actual = result.getResponse().getContentAsByteArray();
        assertArrayEquals(expected, actual, "Suffix range -500 must match last 500 bytes");
    }

    @Test
    @DisplayName("GET stream with unsatisfiable range (bytes=99999999-) returns HTTP 416 Range Not Satisfiable")
    void testRangeUnsatisfiable() throws Exception {
        mockMvc.perform(get("/api/media/stream/ast-drive-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=99999999-"))
                .andExpect(status().isRequestedRangeNotSatisfiable())
                .andExpect(header().string(HttpHeaders.CONTENT_RANGE, "bytes */" + featureBytes.length));
    }

    @Test
    @DisplayName("GET stream for non-existent asset ID returns HTTP 404 MediaNotFoundException")
    void testUnknownAssetReturns404() throws Exception {
        mockMvc.perform(get("/api/media/stream/non-existent-drive-asset"))
                .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("GET stream for asset whose physical file is missing from Drive returns HTTP 404 MediaNotFoundException")
    void testMissingPhysicalFileOnDriveReturns404() throws Exception {
        Movie missingMovie = Movie.builder()
                .id("m4-drive-movie-missing")
                .title("Missing Movie")
                .year(2026)
                .rating(8.0)
                .genres("Animation")
                .build();
        movieRepository.save(missingMovie);

        MediaAsset missingAsset = new MediaAsset(
                "ast-drive-missing-file",
                "m4-drive-movie-missing",
                "feature",
                "drive",
                "movies/m4-drive-movie/v1/does_not_exist.mp4",
                "v1",
                "video/mp4",
                10000L,
                20.0,
                true,
                true
        );
        mediaAssetRepository.save(missingAsset);

        mockMvc.perform(get("/api/media/stream/ast-drive-missing-file"))
                .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("Private Drive asset returns HTTP 404 on GET/HEAD and is omitted from media descriptor")
    void testPrivateDriveAssetIsolation() throws Exception {
        Movie privateMovie = Movie.builder()
                .id("m4-drive-movie-private")
                .title("Private Movie")
                .year(2026)
                .rating(8.0)
                .genres("Drama")
                .build();
        movieRepository.save(privateMovie);

        MediaAsset privateAsset = new MediaAsset(
                "ast-drive-private",
                "m4-drive-movie-private",
                "feature",
                "drive",
                "movies/m4-drive-movie/v1/feature.mp4",
                "v1",
                "video/mp4",
                (long) featureBytes.length,
                25.0,
                false, // private asset
                true
        );
        mediaAssetRepository.save(privateAsset);

        // Direct GET returns 404 with no-cache headers
        mockMvc.perform(get("/api/media/stream/ast-drive-private"))
                .andExpect(status().isNotFound())
                .andExpect(header().string(HttpHeaders.CACHE_CONTROL, containsString("no-cache")))
                .andExpect(header().string(HttpHeaders.CACHE_CONTROL, containsString("no-store")));

        // Direct HEAD returns 404 with no-cache headers
        mockMvc.perform(head("/api/media/stream/ast-drive-private"))
                .andExpect(status().isNotFound())
                .andExpect(header().string(HttpHeaders.CACHE_CONTROL, containsString("no-cache")))
                .andExpect(header().string(HttpHeaders.CACHE_CONTROL, containsString("no-store")));

        // Descriptor does not advertise private feature
        mockMvc.perform(get("/api/movies/m4-drive-movie-private/media-descriptor"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.hasFeature", is(false)))
                .andExpect(jsonPath("$.feature").doesNotExist());
    }

    @Test
    @DisplayName("Drive mount offline returns HTTP 503 MediaUnavailableException on both descriptor and stream")
    void testDriveMountOfflineReturns503() throws Exception {
        Path offlinePath = mockDriveMount.getParent().resolve(mockDriveMount.getFileName().toString() + "-offline");

        try {
            // Simulate unmount / disconnect by renaming mount root
            Files.move(mockDriveMount, offlinePath);
            assertFalse(driveStorageAdapter.isAvailable(), "driveStorageAdapter must report unavailable when mount root is missing");

            // 1. Descriptor request returns HTTP 503
            mockMvc.perform(get("/api/movies/m4-drive-movie/media-descriptor"))
                    .andExpect(status().isServiceUnavailable());

            // 2. Direct stream request returns HTTP 503
            mockMvc.perform(get("/api/media/stream/ast-drive-feat-1"))
                    .andExpect(status().isServiceUnavailable());

        } finally {
            // Restore mount root
            if (Files.exists(offlinePath)) {
                Files.move(offlinePath, mockDriveMount);
            }
            assertTrue(driveStorageAdapter.isAvailable(), "driveStorageAdapter must report available after mount restoration");
        }

        // Verify recovery after mount restoration
        mockMvc.perform(get("/api/movies/m4-drive-movie/media-descriptor"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.hasFeature", is(true)));
    }

    @Test
    @DisplayName("Unconfigured Drive adapter returns isAvailable=false and throws MediaUnavailableException")
    void testUnconfiguredDriveAdapter() {
        DriveMediaStorageAdapter unconfigured = new DriveMediaStorageAdapter("");
        assertFalse(unconfigured.isAvailable());
        assertThrows(MediaUnavailableException.class, () ->
                unconfigured.resolveValidatedPath("movies/m4-drive-movie/v1/feature.mp4"));

        DriveMediaStorageAdapter nullAdapter = new DriveMediaStorageAdapter(null);
        assertFalse(nullAdapter.isAvailable());
        assertThrows(MediaUnavailableException.class, () ->
                nullAdapter.resolveValidatedPath("movies/m4-drive-movie/v1/feature.mp4"));
    }

    @Test
    @DisplayName("Stream concurrency overload returns HTTP 429 Too Many Requests with Retry-After and no-store headers")
    void testDriveStreamConcurrencyLimitAndOverload429() throws Exception {
        int originalLimit = mediaStreamService.getMaxConcurrentDriveStreams();
        try {
            mediaStreamService.setMaxConcurrentDriveStreams(1);
            assertEquals(0, mediaStreamService.getDriveActiveStreamCount());

            // Acquire the single allowed drive stream permit
            assertTrue(mediaStreamService.acquireDriveStreamPermit());
            assertEquals(1, mediaStreamService.getDriveActiveStreamCount());

            // Next stream request MUST be rejected with HTTP 429
            mockMvc.perform(get("/api/media/stream/ast-drive-feat-1"))
                    .andExpect(status().isTooManyRequests())
                    .andExpect(header().string(HttpHeaders.RETRY_AFTER, "5"))
                    .andExpect(header().string(HttpHeaders.CACHE_CONTROL, containsString("no-store")))
                    .andExpect(jsonPath("$.status", is(429)))
                    .andExpect(jsonPath("$.error", is("Too Many Requests")));

            // Active counter remains 1
            assertEquals(1, mediaStreamService.getDriveActiveStreamCount());

            // Release permit
            mediaStreamService.releaseDriveStreamPermit();
            assertEquals(0, mediaStreamService.getDriveActiveStreamCount());

            // Now request succeeds with HTTP 200
            mockMvc.perform(get("/api/media/stream/ast-drive-feat-1"))
                    .andExpect(status().isOk());

            // Counter returns to 0 after completion
            assertEquals(0, mediaStreamService.getDriveActiveStreamCount());
        } finally {
            mediaStreamService.setMaxConcurrentDriveStreams(originalLimit);
        }
    }

    @Test
    @DisplayName("Active stream counter reliably returns to 0 on 200, 206, 404, 416, and 503 outcomes")
    void testObservableStreamCleanupOnAllDriveOutcomes() throws Exception {
        assertEquals(0, mediaStreamService.getDriveActiveStreamCount());
        assertEquals(0, mediaStreamService.getActiveStreamCount());

        // 1. Success full stream -> counter returns to 0
        mockMvc.perform(get("/api/media/stream/ast-drive-feat-1"))
                .andExpect(status().isOk());
        assertEquals(0, mediaStreamService.getDriveActiveStreamCount());
        assertEquals(0, mediaStreamService.getActiveStreamCount());

        // 2. Partial range stream -> counter returns to 0
        mockMvc.perform(get("/api/media/stream/ast-drive-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=0-100"))
                .andExpect(status().isPartialContent());
        assertEquals(0, mediaStreamService.getDriveActiveStreamCount());
        assertEquals(0, mediaStreamService.getActiveStreamCount());

        // 3. Error outcome (404 MediaNotFoundException) -> counter returns to 0
        mockMvc.perform(get("/api/media/stream/non-existent-drive-asset-id"))
                .andExpect(status().isNotFound());
        assertEquals(0, mediaStreamService.getDriveActiveStreamCount());
        assertEquals(0, mediaStreamService.getActiveStreamCount());

        // 4. Invalid range (416 InvalidMediaRangeException) -> counter returns to 0
        mockMvc.perform(get("/api/media/stream/ast-drive-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=999999-9999999"))
                .andExpect(status().isRequestedRangeNotSatisfiable());
        assertEquals(0, mediaStreamService.getDriveActiveStreamCount());
        assertEquals(0, mediaStreamService.getActiveStreamCount());

        // 5. Unmounted / offline outcome (503 MediaUnavailableException) -> counter returns to 0
        Path offlinePath = mockDriveMount.getParent().resolve(mockDriveMount.getFileName().toString() + "-offline-2");
        try {
            Files.move(mockDriveMount, offlinePath);
            mockMvc.perform(get("/api/media/stream/ast-drive-feat-1"))
                    .andExpect(status().isServiceUnavailable());
            assertEquals(0, mediaStreamService.getDriveActiveStreamCount());
            assertEquals(0, mediaStreamService.getActiveStreamCount());
        } finally {
            if (Files.exists(offlinePath)) {
                Files.move(offlinePath, mockDriveMount);
            }
        }
    }
}
