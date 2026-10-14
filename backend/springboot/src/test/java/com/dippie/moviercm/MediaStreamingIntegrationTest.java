package com.dippie.moviercm;

import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.exception.SecurityPathTraversalException;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.service.LocalMediaStorageAdapter;
import com.dippie.moviercm.service.MediaStreamService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import static org.hamcrest.Matchers.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.head;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class MediaStreamingIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private MovieRepository movieRepository;

    @Autowired
    private MediaAssetRepository mediaAssetRepository;

    @Autowired
    private LocalMediaStorageAdapter localStorageAdapter;

    @Autowired
    private MediaStreamService mediaStreamService;

    private long featureTestLength = 0;
    private long trailerTestLength = 0;

    @BeforeEach
    void setupFixtures() throws IOException {
        mediaAssetRepository.deleteAll();
        movieRepository.deleteAll();

        // Ensure test files exist in target/test-media/synthetic
        Path testMediaDir = Paths.get("target", "test-media", "synthetic");
        Files.createDirectories(testMediaDir);

        Path featureFile = testMediaDir.resolve("feature_test.mp4");
        Path trailerFile = testMediaDir.resolve("trailer_test.mp4");

        // If not already copied by pre-step, create minimal dummy content
        if (!Files.exists(featureFile)) {
            byte[] dummyData = new byte[10000];
            for (int i = 0; i < dummyData.length; i++) {
                dummyData[i] = (byte) (i % 128);
            }
            Files.write(featureFile, dummyData);
        }

        if (!Files.exists(trailerFile)) {
            byte[] dummyData = new byte[5000];
            for (int i = 0; i < dummyData.length; i++) {
                dummyData[i] = (byte) (i % 64);
            }
            Files.write(trailerFile, dummyData);
        }

        featureTestLength = Files.size(featureFile);
        trailerTestLength = Files.size(trailerFile);

        // 1. Movie with both feature and trailer
        Movie m1 = Movie.builder()
                .id("test-movie-full")
                .title("Test Movie Full")
                .year(2026)
                .rating(9.0)
                .runtime("1h 45m")
                .genres("Animation,Sci-Fi")
                .description("A movie with both feature film and trailer.")
                .poster("https://example.com/poster.jpg")
                .backdrop("https://example.com/backdrop.jpg")
                .videoUrl("/videos/fallback-full.mp4")
                .build();
        movieRepository.save(m1);

        MediaAsset feat1 = new MediaAsset(
                "ast-test-feat-1",
                "test-movie-full",
                "feature",
                "local",
                "synthetic/feature_test.mp4",
                "v1",
                "video/mp4",
                featureTestLength,
                10.0,
                true,
                true
        );
        MediaAsset trl1 = new MediaAsset(
                "ast-test-trl-1",
                "test-movie-full",
                "trailer",
                "local",
                "synthetic/trailer_test.mp4",
                "v1",
                "video/mp4",
                trailerTestLength,
                3.0,
                true,
                true
        );
        mediaAssetRepository.save(feat1);
        mediaAssetRepository.save(trl1);

        // 2. Movie with trailer only
        Movie m2 = Movie.builder()
                .id("test-movie-trailer-only")
                .title("Test Movie Trailer Only")
                .year(2025)
                .rating(8.0)
                .runtime("2h 00m")
                .genres("Animation")
                .description("A movie with trailer asset only.")
                .poster("https://example.com/p2.jpg")
                .backdrop("https://example.com/b2.jpg")
                .build();
        movieRepository.save(m2);

        MediaAsset trl2 = new MediaAsset(
                "ast-test-trl-2",
                "test-movie-trailer-only",
                "trailer",
                "local",
                "synthetic/trailer_test.mp4",
                "v1",
                "video/mp4",
                trailerTestLength,
                3.0,
                true,
                true
        );
        mediaAssetRepository.save(trl2);

        // 3. Movie with legacy videoUrl only (no media_assets)
        Movie m3 = Movie.builder()
                .id("test-movie-legacy")
                .title("Test Movie Legacy")
                .year(2024)
                .rating(7.5)
                .runtime("1h 30m")
                .genres("Drama")
                .description("Legacy movie using videoUrl fallback.")
                .videoUrl("https://example.com/legacy-trailer.mp4")
                .build();
        movieRepository.save(m3);
    }

    @Test
    @DisplayName("Descriptor returns both feature and trailer when assets exist")
    void testDescriptorWithBothAssets() throws Exception {
        mockMvc.perform(get("/api/movies/test-movie-full/media-descriptor"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.movieId", is("test-movie-full")))
                .andExpect(jsonPath("$.hasFeature", is(true)))
                .andExpect(jsonPath("$.hasTrailer", is(true)))
                .andExpect(jsonPath("$.feature.assetId", is("ast-test-feat-1")))
                .andExpect(jsonPath("$.feature.kind", is("feature")))
                .andExpect(jsonPath("$.feature.streamUrl", is("/api/media/stream/ast-test-feat-1")))
                .andExpect(jsonPath("$.feature.mimeType", is("video/mp4")))
                .andExpect(jsonPath("$.feature.byteLength", is((int) featureTestLength)))
                .andExpect(jsonPath("$.trailer.assetId", is("ast-test-trl-1")))
                .andExpect(jsonPath("$.trailer.kind", is("trailer")));
    }

    @Test
    @DisplayName("Descriptor returns hasFeature=false when movie has trailer only")
    void testDescriptorTrailerOnly() throws Exception {
        mockMvc.perform(get("/api/movies/test-movie-trailer-only/media-descriptor"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.movieId", is("test-movie-trailer-only")))
                .andExpect(jsonPath("$.hasFeature", is(false)))
                .andExpect(jsonPath("$.hasTrailer", is(true)))
                .andExpect(jsonPath("$.feature").doesNotExist())
                .andExpect(jsonPath("$.trailer.assetId", is("ast-test-trl-2")));
    }

    @Test
    @DisplayName("Descriptor provides legacy fallback trailer from videoUrl")
    void testDescriptorLegacyFallback() throws Exception {
        mockMvc.perform(get("/api/movies/test-movie-legacy/media-descriptor"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.movieId", is("test-movie-legacy")))
                .andExpect(jsonPath("$.hasFeature", is(false)))
                .andExpect(jsonPath("$.hasTrailer", is(true)))
                .andExpect(jsonPath("$.trailer.streamUrl", is("https://example.com/legacy-trailer.mp4")))
                .andExpect(jsonPath("$.trailer.version", is("legacy")));
    }

    @Test
    @DisplayName("Descriptor returns 404 for non-existent movie")
    void testDescriptorNotFound() throws Exception {
        mockMvc.perform(get("/api/movies/non-existent-movie-id/media-descriptor"))
                .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("HEAD request returns headers without body")
    void testHeadStreamingHeaders() throws Exception {
        mockMvc.perform(head("/api/media/stream/ast-test-feat-1"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.CONTENT_TYPE, "video/mp4"))
                .andExpect(header().string(HttpHeaders.ACCEPT_RANGES, "bytes"))
                .andExpect(header().string(HttpHeaders.CONTENT_LENGTH, String.valueOf(featureTestLength)))
                .andExpect(header().exists(HttpHeaders.ETAG));
    }

    @Test
    @DisplayName("GET stream without Range header returns 200 and entire content")
    void testFullStreamWithoutRange() throws Exception {
        mockMvc.perform(get("/api/media/stream/ast-test-feat-1"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.CONTENT_TYPE, "video/mp4"))
                .andExpect(header().string(HttpHeaders.ACCEPT_RANGES, "bytes"))
                .andExpect(header().string(HttpHeaders.CONTENT_LENGTH, String.valueOf(featureTestLength)));
    }

    @Test
    @DisplayName("GET stream with closed range returns 206 Partial Content")
    void testClosedRangeStream() throws Exception {
        mockMvc.perform(get("/api/media/stream/ast-test-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=0-1023"))
                .andExpect(status().isPartialContent())
                .andExpect(header().string(HttpHeaders.ACCEPT_RANGES, "bytes"))
                .andExpect(header().string(HttpHeaders.CONTENT_RANGE, containsString("bytes 0-1023/" + featureTestLength)))
                .andExpect(header().string(HttpHeaders.CONTENT_LENGTH, "1024"));
    }

    @Test
    @DisplayName("GET stream with open-ended range returns 206 Partial Content")
    void testOpenEndedRangeStream() throws Exception {
        long start = 1000;
        long expectedLength = featureTestLength - start;
        long expectedEnd = featureTestLength - 1;

        mockMvc.perform(get("/api/media/stream/ast-test-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=" + start + "-"))
                .andExpect(status().isPartialContent())
                .andExpect(header().string(HttpHeaders.CONTENT_RANGE, containsString("bytes " + start + "-" + expectedEnd + "/" + featureTestLength)))
                .andExpect(header().string(HttpHeaders.CONTENT_LENGTH, String.valueOf(expectedLength)));
    }

    @Test
    @DisplayName("GET stream with suffix range returns 206 Partial Content")
    void testSuffixRangeStream() throws Exception {
        long suffix = 500;
        long expectedStart = featureTestLength - suffix;
        long expectedEnd = featureTestLength - 1;

        mockMvc.perform(get("/api/media/stream/ast-test-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=-" + suffix))
                .andExpect(status().isPartialContent())
                .andExpect(header().string(HttpHeaders.CONTENT_RANGE, containsString("bytes " + expectedStart + "-" + expectedEnd + "/" + featureTestLength)))
                .andExpect(header().string(HttpHeaders.CONTENT_LENGTH, String.valueOf(suffix)));
    }

    @Test
    @DisplayName("GET stream with unsatisfiable range returns 416 Range Not Satisfiable")
    void testUnsatisfiableRangeStream() throws Exception {
        mockMvc.perform(get("/api/media/stream/ast-test-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=99999999-"))
                .andExpect(status().isRequestedRangeNotSatisfiable())
                .andExpect(header().string(HttpHeaders.CONTENT_RANGE, "bytes */" + featureTestLength));
    }

    @Test
    @DisplayName("GET stream for unknown asset returns 404")
    void testUnknownAssetStream() throws Exception {
        mockMvc.perform(get("/api/media/stream/non-existent-asset"))
                .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("Storage adapter strictly rejects path traversal and drive letters")
    void testSecurityPathTraversalRejection() {
        assertThrows(SecurityPathTraversalException.class, () ->
                localStorageAdapter.resolveValidatedPath("../../secret.txt"));

        assertThrows(SecurityPathTraversalException.class, () ->
                localStorageAdapter.resolveValidatedPath("..\\..\\Windows\\System32\\cmd.exe"));

        assertThrows(SecurityPathTraversalException.class, () ->
                localStorageAdapter.resolveValidatedPath("C:\\Windows\\System32\\calc.exe"));

        assertThrows(SecurityPathTraversalException.class, () ->
                localStorageAdapter.resolveValidatedPath("/etc/passwd"));

        assertThrows(SecurityPathTraversalException.class, () ->
                localStorageAdapter.resolveValidatedPath("synthetic/feature_test.mp4\0.txt"));
    }

    @Test
    @DisplayName("Private assets return 404 and no-cache on direct GET and HEAD, and are not in descriptor")
    void testPrivateAssetIsolation() throws Exception {
        Movie mPrivate = Movie.builder()
                .id("test-movie-private")
                .title("Private Movie")
                .year(2026)
                .rating(8.0)
                .genres("Drama")
                .build();
        movieRepository.save(mPrivate);

        MediaAsset privateFeat = new MediaAsset(
                "ast-test-private-1",
                "test-movie-private",
                "feature",
                "local",
                "synthetic/feature_test.mp4",
                "v1",
                "video/mp4",
                featureTestLength,
                10.0,
                false,
                true
        );
        mediaAssetRepository.save(privateFeat);

        // Direct GET returns 404 with no-cache headers
        mockMvc.perform(get("/api/media/stream/ast-test-private-1"))
                .andExpect(status().isNotFound())
                .andExpect(header().string(HttpHeaders.CACHE_CONTROL, containsString("no-cache")))
                .andExpect(header().string(HttpHeaders.CACHE_CONTROL, containsString("no-store")));

        // Direct HEAD returns 404 with no-cache headers
        mockMvc.perform(head("/api/media/stream/ast-test-private-1"))
                .andExpect(status().isNotFound())
                .andExpect(header().string(HttpHeaders.CACHE_CONTROL, containsString("no-cache")))
                .andExpect(header().string(HttpHeaders.CACHE_CONTROL, containsString("no-store")));

        // In descriptor, private asset is not advertised
        mockMvc.perform(get("/api/movies/test-movie-private/media-descriptor"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.hasFeature", is(false)))
                .andExpect(jsonPath("$.feature").doesNotExist());
    }

    @Test
    @DisplayName("Descriptor serializes isPublic field strictly as isPublic")
    void testDescriptorIsPublicSerialization() throws Exception {
        mockMvc.perform(get("/api/movies/test-movie-full/media-descriptor"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.feature.isPublic", is(true)))
                .andExpect(jsonPath("$.feature.public").doesNotExist());
    }

    @Test
    @DisplayName("Missing media root throws 503 MediaUnavailableException without creating directories on read")
    void testMissingRootThrows503WithoutCreatingDir() {
        Path nonExistentRoot = Paths.get("target", "non-existent-media-root-" + System.nanoTime());
        org.junit.jupiter.api.Assertions.assertFalse(Files.exists(nonExistentRoot));

        LocalMediaStorageAdapter adapter = new LocalMediaStorageAdapter(nonExistentRoot.toString());
        org.junit.jupiter.api.Assertions.assertFalse(adapter.isAvailable());

        assertThrows(MediaUnavailableException.class, () ->
                adapter.resolveValidatedPath("test.mp4"));

        // Crucial: verify no directories were created on disk
        org.junit.jupiter.api.Assertions.assertFalse(Files.exists(nonExistentRoot));
    }

    @Test
    @DisplayName("Unknown storage provider throws MediaUnavailableException (503)")
    void testUnknownStorageProviderThrowsUnavailable() {
        assertThrows(MediaUnavailableException.class, () ->
                mediaStreamService.getStorageAdapter("unknown-cloud-storage"));
    }

    @Test
    @DisplayName("F2: Saturated concurrency returns 429 Too Many Requests with Retry-After and no-store headers")
    void testMediaStreamConcurrencyLimitAndOverload429() throws Exception {
        int originalLimit = mediaStreamService.getMaxConcurrentStreams();
        try {
            // Configure concurrency limit to 1
            mediaStreamService.setMaxConcurrentStreams(1);
            assertEquals(0, mediaStreamService.getActiveStreamCount());

            // Acquire 1 permit (holding the single allowed stream)
            assertTrue(mediaStreamService.acquireStreamPermit());
            assertEquals(1, mediaStreamService.getActiveStreamCount());

            // Next stream request MUST be rejected with HTTP 429
            mockMvc.perform(get("/api/media/stream/ast-test-feat-1"))
                    .andExpect(status().isTooManyRequests())
                    .andExpect(header().string(HttpHeaders.RETRY_AFTER, "5"))
                    .andExpect(header().string(HttpHeaders.CACHE_CONTROL, containsString("no-store")))
                    .andExpect(jsonPath("$.status", is(429)))
                    .andExpect(jsonPath("$.error", is("Too Many Requests")));

            // Active counter must still be 1 (the held permit)
            assertEquals(1, mediaStreamService.getActiveStreamCount());
            assertTrue(mediaStreamService.getTotalRejectedCount() >= 1);

            // Release held permit
            mediaStreamService.releaseStreamPermit();
            assertEquals(0, mediaStreamService.getActiveStreamCount());

            // Now request should succeed with 200 OK
            mockMvc.perform(get("/api/media/stream/ast-test-feat-1"))
                    .andExpect(status().isOk());

            // And counter returns to 0 after completion
            assertEquals(0, mediaStreamService.getActiveStreamCount());
        } finally {
            mediaStreamService.setMaxConcurrentStreams(originalLimit);
        }
    }

    @Test
    @DisplayName("F2: Active stream counter reliably returns to 0 on success, partial range, and 404/503 errors")
    void testObservableStreamCleanupOnAllOutcomes() throws Exception {
        assertEquals(0, mediaStreamService.getActiveStreamCount());

        // 1. Success full stream -> counter returns to 0
        mockMvc.perform(get("/api/media/stream/ast-test-feat-1"))
                .andExpect(status().isOk());
        assertEquals(0, mediaStreamService.getActiveStreamCount());

        // 2. Partial range stream -> counter returns to 0
        mockMvc.perform(get("/api/media/stream/ast-test-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=0-10"))
                .andExpect(status().isPartialContent());
        assertEquals(0, mediaStreamService.getActiveStreamCount());

        // 3. Error outcome (404 MediaNotFoundException) -> counter returns to 0
        mockMvc.perform(get("/api/media/stream/non-existent-asset-id"))
                .andExpect(status().isNotFound());
        assertEquals(0, mediaStreamService.getActiveStreamCount());

        // 4. Invalid range (416 InvalidMediaRangeException) -> counter returns to 0
        mockMvc.perform(get("/api/media/stream/ast-test-feat-1")
                        .header(HttpHeaders.RANGE, "bytes=999999-9999999"))
                .andExpect(status().isRequestedRangeNotSatisfiable());
        assertEquals(0, mediaStreamService.getActiveStreamCount());
    }
}
