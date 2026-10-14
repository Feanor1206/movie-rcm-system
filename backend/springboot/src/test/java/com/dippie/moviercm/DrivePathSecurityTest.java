package com.dippie.moviercm;

import com.dippie.moviercm.exception.MediaNotFoundException;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.exception.SecurityPathTraversalException;
import com.dippie.moviercm.service.DriveMediaStorageAdapter;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.core.io.Resource;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("DrivePathSecurityTest - Comprehensive IO Failure and Security Verification")
public class DrivePathSecurityTest {

    @TempDir
    Path tempMountDir;

    @TempDir
    Path tempOutsideDir;

    private DriveMediaStorageAdapter adapter;

    @BeforeEach
    void setUp() {
        adapter = new DriveMediaStorageAdapter(tempMountDir.toString());
    }

    @Nested
    @DisplayName("1. Null Byte Injection Tests")
    class NullByteInjectionTests {

        private final List<String> nullByteVectors = List.of(
                "test\0.mp4",
                "movies/\0/video.mp4",
                "\0test.mp4",
                "movies/feature.mp4\0",
                "movies/trailer\0.mp4",
                "movies/2026/\0file.mp4"
        );

        @Test
        @DisplayName("Rejects null byte injection in resolveValidatedPath and all channel/resource methods")
        void testNullByteVectorsRejected() {
            for (String vector : nullByteVectors) {
                SecurityPathTraversalException ex = assertThrows(
                        SecurityPathTraversalException.class,
                        () -> adapter.resolveValidatedPath(vector),
                        "Expected SecurityPathTraversalException for vector: " + vector
                );
                assertTrue(ex.getMessage().contains("null byte") || ex.getMessage().contains("không hợp lệ"),
                        "Exception message should mention null byte: " + ex.getMessage());

                // Ensure all consumer methods enforce the same boundary
                assertThrows(SecurityPathTraversalException.class, () -> adapter.getResource(vector));
                assertThrows(SecurityPathTraversalException.class, () -> adapter.getResourceLength(vector));
                assertThrows(SecurityPathTraversalException.class, () -> adapter.openChannel(vector));
            }
        }
    }

    @Nested
    @DisplayName("2. Path Traversal Tests")
    class PathTraversalTests {

        private final List<String> traversalVectors = List.of(
                "..",
                "../etc/passwd",
                "foo/../../bar",
                "....//....//",
                "..../..../",
                "movies/normal/../../../secret.txt",
                "movies/../../secret.mp4",
                "sub/..",
                "..\\..\\Windows\\System32\\cmd.exe",
                "movies/../../../../boot.ini",
                "a/b/../../../c"
        );

        @Test
        @DisplayName("Rejects standard, nested, normalized, and redundant path traversal patterns")
        void testPathTraversalVectorsRejected() {
            for (String vector : traversalVectors) {
                SecurityPathTraversalException ex = assertThrows(
                        SecurityPathTraversalException.class,
                        () -> adapter.resolveValidatedPath(vector),
                        "Expected SecurityPathTraversalException for traversal vector: " + vector
                );
                assertNotNull(ex.getMessage());

                // Boundary invariant across all entry points
                assertThrows(SecurityPathTraversalException.class, () -> adapter.getResource(vector));
                assertThrows(SecurityPathTraversalException.class, () -> adapter.getResourceLength(vector));
                assertThrows(SecurityPathTraversalException.class, () -> adapter.openChannel(vector));
            }
        }
    }

    @Nested
    @DisplayName("3. Windows Drive Letters Tests")
    class WindowsDriveLettersTests {

        private final List<String> driveLetterVectors = List.of(
                "C:\\Windows\\System32\\cmd.exe",
                "D:movie.mp4",
                "c:/movies/1.mp4",
                "d:\\data\\secret.mp4",
                "E:test.mp4",
                "Z:\\secret.dat"
        );

        @Test
        @DisplayName("Rejects Windows drive letter absolute and relative-to-drive paths")
        void testDriveLetterVectorsRejected() {
            for (String vector : driveLetterVectors) {
                SecurityPathTraversalException ex = assertThrows(
                        SecurityPathTraversalException.class,
                        () -> adapter.resolveValidatedPath(vector),
                        "Expected SecurityPathTraversalException for drive letter vector: " + vector
                );
                assertNotNull(ex.getMessage());

                assertThrows(SecurityPathTraversalException.class, () -> adapter.getResource(vector));
                assertThrows(SecurityPathTraversalException.class, () -> adapter.getResourceLength(vector));
                assertThrows(SecurityPathTraversalException.class, () -> adapter.openChannel(vector));
            }
        }
    }

    @Nested
    @DisplayName("4. Absolute Paths Tests")
    class AbsolutePathsTests {

        private final List<String> absolutePathVectors = List.of(
                "/movies/1.mp4",
                "\\movies\\1.mp4",
                "/etc/passwd",
                "\\Windows\\System32",
                "/root/secrets.env",
                "\\temp\\malware.exe"
        );

        @Test
        @DisplayName("Rejects Unix and Windows root-relative absolute paths")
        void testAbsolutePathVectorsRejected() {
            for (String vector : absolutePathVectors) {
                SecurityPathTraversalException ex = assertThrows(
                        SecurityPathTraversalException.class,
                        () -> adapter.resolveValidatedPath(vector),
                        "Expected SecurityPathTraversalException for absolute path vector: " + vector
                );
                assertNotNull(ex.getMessage());

                assertThrows(SecurityPathTraversalException.class, () -> adapter.getResource(vector));
                assertThrows(SecurityPathTraversalException.class, () -> adapter.getResourceLength(vector));
                assertThrows(SecurityPathTraversalException.class, () -> adapter.openChannel(vector));
            }
        }
    }

    @Nested
    @DisplayName("5. UNC Paths Tests")
    class UncPathsTests {

        private final List<String> uncVectors = List.of(
                "\\\\attacker-server\\share\\file.mp4",
                "//attacker-server/share/file.mp4",
                "\\\\192.168.1.100\\c$\\windows\\system32",
                "//127.0.0.1/c$/boot.ini"
        );

        @Test
        @DisplayName("Rejects SMB/UNC remote network paths")
        void testUncVectorsRejected() {
            for (String vector : uncVectors) {
                SecurityPathTraversalException ex = assertThrows(
                        SecurityPathTraversalException.class,
                        () -> adapter.resolveValidatedPath(vector),
                        "Expected SecurityPathTraversalException for UNC vector: " + vector
                );
                assertNotNull(ex.getMessage());

                assertThrows(SecurityPathTraversalException.class, () -> adapter.getResource(vector));
                assertThrows(SecurityPathTraversalException.class, () -> adapter.getResourceLength(vector));
                assertThrows(SecurityPathTraversalException.class, () -> adapter.openChannel(vector));
            }
        }
    }

    @Nested
    @DisplayName("6. Windows NT Device Namespace Tests")
    class WindowsNtDeviceNamespaceTests {

        private final List<String> deviceNamespaceVectors = List.of(
                "\\\\.\\PhysicalDrive0",
                "\\\\?\\Volume{123}\\file.mp4",
                "\\\\?\\C:\\test.mp4",
                "\\\\.\\COM1",
                "\\\\.\\NUL",
                "\\\\.\\Pipe\\NamedPipe"
        );

        @Test
        @DisplayName("Rejects Windows NT device namespace and DOS device prefixes")
        void testDeviceNamespaceVectorsRejected() {
            for (String vector : deviceNamespaceVectors) {
                SecurityPathTraversalException ex = assertThrows(
                        SecurityPathTraversalException.class,
                        () -> adapter.resolveValidatedPath(vector),
                        "Expected SecurityPathTraversalException for device namespace vector: " + vector
                );
                assertNotNull(ex.getMessage());

                assertThrows(SecurityPathTraversalException.class, () -> adapter.getResource(vector));
                assertThrows(SecurityPathTraversalException.class, () -> adapter.getResourceLength(vector));
                assertThrows(SecurityPathTraversalException.class, () -> adapter.openChannel(vector));
            }
        }
    }

    @Nested
    @DisplayName("7. Symlink and Junction Escaping Tests")
    class SymlinkEscapingTests {

        @Test
        @DisplayName("Symlink or junction escaping root mount throws SecurityPathTraversalException")
        void testSymlinkEscapingDetection() throws Exception {
            // Setup outside secret file
            Path outsideSecret = tempOutsideDir.resolve("outside_secret.mp4");
            Files.writeString(outsideSecret, "RESTRICTED_OUTSIDE_VIDEO_PAYLOAD");

            // 1. File symlink attempt
            boolean fileSymlinkCreated = false;
            Path symlinkFile = tempMountDir.resolve("symlink_escape.mp4");
            try {
                Files.createSymbolicLink(symlinkFile, outsideSecret);
                fileSymlinkCreated = true;
            } catch (UnsupportedOperationException | IOException | SecurityException e) {
                // Windows non-elevated developer mode may disallow file symlinks; safely caught
                System.out.println("Notice: File symlink creation restricted by Windows OS privileges: " + e.getMessage());
            }

            if (fileSymlinkCreated) {
                assertThrows(SecurityPathTraversalException.class, () ->
                        adapter.resolveValidatedPath("symlink_escape.mp4"));
                assertThrows(SecurityPathTraversalException.class, () ->
                        adapter.getResource("symlink_escape.mp4"));
                assertThrows(SecurityPathTraversalException.class, () ->
                        adapter.openChannel("symlink_escape.mp4"));
            }

            // 2. Directory junction attempt (always supported on Windows NTFS without elevation)
            String os = System.getProperty("os.name").toLowerCase();
            if (os.contains("win")) {
                Path junctionDir = tempMountDir.resolve("outside_junction");
                try {
                    Process process = new ProcessBuilder(
                            "cmd", "/c", "mklink", "/J",
                            junctionDir.toAbsolutePath().toString(),
                            tempOutsideDir.toAbsolutePath().toString()
                    ).redirectErrorStream(true).start();

                    int exitCode = process.waitFor();
                    if (exitCode == 0 && Files.exists(junctionDir)) {
                        assertThrows(SecurityPathTraversalException.class, () ->
                                adapter.resolveValidatedPath("outside_junction/outside_secret.mp4"));
                        assertThrows(SecurityPathTraversalException.class, () ->
                                adapter.getResource("outside_junction/outside_secret.mp4"));
                        assertThrows(SecurityPathTraversalException.class, () ->
                                adapter.openChannel("outside_junction/outside_secret.mp4"));
                    } else {
                        System.out.println("Notice: mklink /J did not complete with code 0; junction skipped.");
                    }
                } catch (Exception e) {
                    System.out.println("Notice: mklink junction execution caught: " + e.getMessage());
                }
            }
        }
    }

    @Nested
    @DisplayName("8. Valid Path in Subdirectory Tests")
    class ValidSubdirectoryTests {

        @Test
        @DisplayName("Valid relative path in nested subfolder resolves correctly and permits random access read")
        void testValidNestedSubdirectoryFile() throws IOException {
            Path nestedDir = tempMountDir.resolve("movies/m1/v1");
            Files.createDirectories(nestedDir);

            Path featureFile = nestedDir.resolve("feature.mp4");
            byte[] expectedData = "VALID_GDRIVE_STREAM_FEATURE_CONTENT_123456789".getBytes(StandardCharsets.UTF_8);
            Files.write(featureFile, expectedData);

            // 1. resolveValidatedPath
            Path resolved = adapter.resolveValidatedPath("movies/m1/v1/feature.mp4");
            assertEquals(featureFile.toRealPath(), resolved, "Resolved path must match exact canonical real path");

            // 2. getResource
            Resource resource = adapter.getResource("movies/m1/v1/feature.mp4");
            assertNotNull(resource);
            assertTrue(resource.exists());
            assertTrue(resource.isReadable());
            assertEquals(expectedData.length, resource.contentLength());

            // 3. getResourceLength
            long length = adapter.getResourceLength("movies/m1/v1/feature.mp4");
            assertEquals(expectedData.length, length);

            // 4. openChannel & Random-access seek
            try (SeekableByteChannel channel = adapter.openChannel("movies/m1/v1/feature.mp4")) {
                assertEquals(expectedData.length, channel.size());

                ByteBuffer buffer = ByteBuffer.allocate(expectedData.length);
                int read = channel.read(buffer);
                assertEquals(expectedData.length, read);
                assertArrayEquals(expectedData, buffer.array());

                // Random access seek test
                int seekPos = 10;
                channel.position(seekPos);
                assertEquals(seekPos, channel.position());

                ByteBuffer tailBuffer = ByteBuffer.allocate(expectedData.length - seekPos);
                int tailRead = channel.read(tailBuffer);
                assertEquals(expectedData.length - seekPos, tailRead);

                byte[] expectedTail = new byte[expectedData.length - seekPos];
                System.arraycopy(expectedData, seekPos, expectedTail, 0, expectedTail.length);
                assertArrayEquals(expectedTail, tailBuffer.array());
            }
        }
    }

    @Nested
    @DisplayName("9. Read-Only Invariant and Non-Existent Path Tests")
    class ReadOnlyAndMissingTests {

        @Test
        @DisplayName("Missing file throws MediaNotFoundException without mutating filesystem")
        void testMissingFileThrowsNotFound() throws IOException {
            Path initialDir = tempMountDir.resolve("movies/sub");
            Files.createDirectories(initialDir);
            Path existingFile = initialDir.resolve("existing.mp4");
            Files.writeString(existingFile, "content");

            Set<Path> beforeSnapshot = takeSnapshot(tempMountDir);

            assertThrows(MediaNotFoundException.class, () ->
                    adapter.resolveValidatedPath("movies/sub/non_existent.mp4"));

            assertThrows(MediaNotFoundException.class, () ->
                    adapter.getResource("movies/sub/non_existent.mp4"));

            assertThrows(MediaNotFoundException.class, () ->
                    adapter.getResourceLength("movies/sub/non_existent.mp4"));

            assertThrows(MediaNotFoundException.class, () ->
                    adapter.openChannel("movies/sub/non_existent.mp4"));

            Set<Path> afterSnapshot = takeSnapshot(tempMountDir);
            assertEquals(beforeSnapshot, afterSnapshot, "Adapter must be strictly read-only and never create files or folders");
        }

        @Test
        @DisplayName("Unconfigured or offline adapter throws MediaUnavailableException")
        void testOfflineAdapter() {
            DriveMediaStorageAdapter unconfigured = new DriveMediaStorageAdapter("");
            assertFalse(unconfigured.isAvailable());
            assertThrows(MediaUnavailableException.class, () ->
                    unconfigured.resolveValidatedPath("movies/m1/v1/feature.mp4"));

            Path missingDir = tempMountDir.resolve("does_not_exist_drive_dir");
            DriveMediaStorageAdapter offline = new DriveMediaStorageAdapter(missingDir.toString());
            assertFalse(offline.isAvailable());
            assertThrows(MediaUnavailableException.class, () ->
                    offline.resolveValidatedPath("movies/m1/v1/feature.mp4"));
        }

        private Set<Path> takeSnapshot(Path dir) throws IOException {
            try (Stream<Path> stream = Files.walk(dir)) {
                return stream.collect(Collectors.toSet());
            }
        }
    }
}
