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
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("DriveMediaStorageAdapter Unit Tests")
class DriveMediaStorageAdapterTest {

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
    @DisplayName("1. Unconfigured Mount Tests")
    class UnconfiguredMountTests {

        @Test
        @DisplayName("Null or empty or whitespace mount path returns isAvailable false and throws 503")
        void testUnconfiguredMountPath() {
            String[] unconfiguredPaths = {null, "", "   ", "\t\n"};

            for (String mountPath : unconfiguredPaths) {
                DriveMediaStorageAdapter unconfiguredAdapter = new DriveMediaStorageAdapter(mountPath);

                assertEquals("drive", unconfiguredAdapter.getProviderName());
                assertFalse(unconfiguredAdapter.isAvailable(), "Mount with path [" + mountPath + "] should not be available");

                assertThrows(MediaUnavailableException.class, () ->
                        unconfiguredAdapter.resolveValidatedPath("sample/movie.mp4"));

                assertThrows(MediaUnavailableException.class, () ->
                        unconfiguredAdapter.getResource("sample/movie.mp4"));

                assertThrows(MediaUnavailableException.class, () ->
                        unconfiguredAdapter.getResourceLength("sample/movie.mp4"));

                assertThrows(MediaUnavailableException.class, () ->
                        unconfiguredAdapter.openChannel("sample/movie.mp4"));
            }
        }
    }

    @Nested
    @DisplayName("2. Non-existent or Invalid Mount Path Tests")
    class InvalidMountPathTests {

        @Test
        @DisplayName("Non-existent directory path returns isAvailable false and throws 503")
        void testNonExistentMountPath() {
            Path nonExistent = tempMountDir.resolve("missing_drive_mount_dir");
            DriveMediaStorageAdapter missingAdapter = new DriveMediaStorageAdapter(nonExistent.toString());

            assertFalse(missingAdapter.isAvailable());

            assertThrows(MediaUnavailableException.class, () ->
                    missingAdapter.resolveValidatedPath("test.mp4"));

            assertThrows(MediaUnavailableException.class, () ->
                    missingAdapter.getResource("test.mp4"));

            assertThrows(MediaUnavailableException.class, () ->
                    missingAdapter.getResourceLength("test.mp4"));

            assertThrows(MediaUnavailableException.class, () ->
                    missingAdapter.openChannel("test.mp4"));
        }

        @Test
        @DisplayName("Mount path pointing to a regular file instead of a directory returns isAvailable false and throws 503")
        void testFileAsMountPath() throws IOException {
            Path regularFile = tempMountDir.resolve("not_a_dir.txt");
            Files.writeString(regularFile, "not a directory");

            DriveMediaStorageAdapter fileAdapter = new DriveMediaStorageAdapter(regularFile.toString());

            assertFalse(fileAdapter.isAvailable());

            assertThrows(MediaUnavailableException.class, () ->
                    fileAdapter.resolveValidatedPath("test.mp4"));
        }
    }

    @Nested
    @DisplayName("3. Valid Mount Path Tests")
    class ValidMountPathTests {

        @Test
        @DisplayName("Valid mount directory returns isAvailable true")
        void testValidMountAvailability() {
            assertTrue(adapter.isAvailable());
            assertEquals("drive", adapter.getProviderName());
        }
    }

    @Nested
    @DisplayName("4. Path Traversal & Sanitization Tests")
    class PathTraversalTests {

        @Test
        @DisplayName("Rejects null, empty, or whitespace relative paths")
        void testEmptyRelativePaths() {
            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath(null));

            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath(""));

            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("   "));
        }

        @Test
        @DisplayName("Rejects null byte injection")
        void testNullByteRejection() {
            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("movies/feature.mp4\0.txt"));

            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("\0secret.mp4"));
        }

        @Test
        @DisplayName("Rejects relative directory traversal patterns")
        void testDirectoryTraversalRejection() {
            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("../../secret.txt"));

            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("..\\..\\Windows\\System32\\cmd.exe"));

            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("movies/../../../etc/passwd"));

            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("sub/.."));
        }

        @Test
        @DisplayName("Rejects absolute paths and Windows drive letters")
        void testAbsolutePathsAndDriveLetters() {
            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("C:\\Windows\\System32\\calc.exe"));

            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("D:movie.mp4"));

            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("c:/test.mp4"));

            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("/etc/passwd"));

            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("\\Windows\\System32"));
        }

        @Test
        @DisplayName("Rejects UNC paths and device namespaces")
        void testUncAndDevicePaths() {
            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("\\\\server\\share\\movie.mp4"));

            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("\\\\?\\C:\\test.mp4"));

            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("\\\\.\\PhysicalDrive0"));
        }
    }

    @Nested
    @DisplayName("5. Symlink & Reparse Point Boundary Tests")
    class SymlinkBoundaryTests {

        @Test
        @DisplayName("Reparse point or symlink escaping root mount throws SecurityPathTraversalException")
        void testSymlinkEscapesRoot() throws Exception {
            Path outsideFile = tempOutsideDir.resolve("secret_outside.mp4");
            Files.writeString(outsideFile, "confidential video payload outside root");

            boolean symlinkCreated = false;
            Path symlinkInMount = tempMountDir.resolve("symlink_escape.mp4");
            try {
                Files.createSymbolicLink(symlinkInMount, outsideFile);
                symlinkCreated = true;
            } catch (UnsupportedOperationException | IOException | SecurityException ignored) {
                // Windows non-elevated environments might disallow file symlinks
            }

            if (symlinkCreated) {
                assertThrows(SecurityPathTraversalException.class, () ->
                        adapter.resolveValidatedPath("symlink_escape.mp4"));
            }

            // Always test directory junction which is universally supported on Windows NTFS
            String os = System.getProperty("os.name").toLowerCase();
            if (os.contains("win")) {
                Path junctionDir = tempMountDir.resolve("outside_junction");
                Process process = new ProcessBuilder(
                        "cmd", "/c", "mklink", "/J",
                        junctionDir.toAbsolutePath().toString(),
                        tempOutsideDir.toAbsolutePath().toString()
                ).redirectErrorStream(true).start();

                int exitCode = process.waitFor();
                if (exitCode == 0) {
                    assertThrows(SecurityPathTraversalException.class, () ->
                            adapter.resolveValidatedPath("outside_junction/secret_outside.mp4"));
                }
            }
        }
    }

    @Nested
    @DisplayName("6. Non-existent Media in Valid Mount Tests")
    class NotFoundTests {

        @Test
        @DisplayName("Non-existent file throws MediaNotFoundException (404)")
        void testNonExistentFileThrows404() {
            assertThrows(MediaNotFoundException.class, () ->
                    adapter.resolveValidatedPath("movies/missing.mp4"));

            assertThrows(MediaNotFoundException.class, () ->
                    adapter.getResource("movies/missing.mp4"));

            assertThrows(MediaNotFoundException.class, () ->
                    adapter.getResourceLength("movies/missing.mp4"));

            assertThrows(MediaNotFoundException.class, () ->
                    adapter.openChannel("movies/missing.mp4"));
        }

        @Test
        @DisplayName("Directory path instead of regular file throws MediaNotFoundException")
        void testDirectoryPathThrowsNotFound() throws IOException {
            Path subDir = tempMountDir.resolve("subfolder");
            Files.createDirectories(subDir);

            assertThrows(MediaNotFoundException.class, () ->
                    adapter.resolveValidatedPath("subfolder"));
        }
    }

    @Nested
    @DisplayName("7. Valid File Operations & Channel Seek Tests")
    class ValidFileOperationsTests {

        @Test
        @DisplayName("Valid file returns resource, exact length, and SeekableByteChannel with random access")
        void testValidFileReadAndSeek() throws IOException {
            Path movieDir = tempMountDir.resolve("movies/2026");
            Files.createDirectories(movieDir);
            Path movieFile = movieDir.resolve("sample_feature.mp4");

            byte[] expectedData = "DRIVE-STREAMING-TEST-PAYLOAD-0123456789-RANDOM-ACCESS-VERIFIED".getBytes(StandardCharsets.UTF_8);
            Files.write(movieFile, expectedData);

            // 1. resolveValidatedPath
            Path resolved = adapter.resolveValidatedPath("movies/2026/sample_feature.mp4");
            assertEquals(movieFile.toRealPath(), resolved);

            // 2. getResource
            Resource resource = adapter.getResource("movies/2026/sample_feature.mp4");
            assertNotNull(resource);
            assertTrue(resource.exists());
            assertTrue(resource.isReadable());
            assertEquals(expectedData.length, resource.contentLength());

            // 3. getResourceLength
            long length = adapter.getResourceLength("movies/2026/sample_feature.mp4");
            assertEquals(expectedData.length, length);

            // 4. openChannel & Random Access Seek
            try (SeekableByteChannel channel = adapter.openChannel("movies/2026/sample_feature.mp4")) {
                assertEquals(expectedData.length, channel.size());

                // Read full content from start
                ByteBuffer buffer = ByteBuffer.allocate(expectedData.length);
                int bytesRead = channel.read(buffer);
                assertEquals(expectedData.length, bytesRead);
                assertArrayEquals(expectedData, buffer.array());

                // Seek test: position at offset 16 ("TEST-PAYLOAD-...")
                int seekOffset = 16;
                channel.position(seekOffset);
                assertEquals(seekOffset, channel.position());

                ByteBuffer remainingBuffer = ByteBuffer.allocate(expectedData.length - seekOffset);
                int remainingRead = channel.read(remainingBuffer);
                assertEquals(expectedData.length - seekOffset, remainingRead);

                byte[] expectedTail = new byte[expectedData.length - seekOffset];
                System.arraycopy(expectedData, seekOffset, expectedTail, 0, expectedTail.length);
                assertArrayEquals(expectedTail, remainingBuffer.array());
            }
        }
    }

    @Nested
    @DisplayName("8. Read-Only Invariant Tests")
    class ReadOnlyInvariantTests {

        @Test
        @DisplayName("Adapter operations are strictly read-only and never create files or directories")
        void testMountRemainsUntouchedDuringAllOperations() throws IOException {
            // Setup an initial known state
            Path initialSubDir = tempMountDir.resolve("initial_folder");
            Files.createDirectories(initialSubDir);
            Path initialFile = initialSubDir.resolve("existing.mp4");
            Files.writeString(initialFile, "existing content");

            Set<Path> snapshotBefore = takeDirectorySnapshot(tempMountDir);

            // Execute read operations on valid file
            assertTrue(adapter.isAvailable());
            adapter.resolveValidatedPath("initial_folder/existing.mp4");
            adapter.getResource("initial_folder/existing.mp4");
            adapter.getResourceLength("initial_folder/existing.mp4");
            try (SeekableByteChannel channel = adapter.openChannel("initial_folder/existing.mp4")) {
                ByteBuffer buf = ByteBuffer.allocate(8);
                channel.read(buf);
            }

            // Execute queries on non-existent files and directories
            assertThrows(MediaNotFoundException.class, () ->
                    adapter.resolveValidatedPath("non_existent_folder/missing.mp4"));
            assertThrows(MediaNotFoundException.class, () ->
                    adapter.getResource("ghost_directory/ghost_file.mp4"));

            // Execute traversal attempts
            assertThrows(SecurityPathTraversalException.class, () ->
                    adapter.resolveValidatedPath("../../secret.txt"));

            Set<Path> snapshotAfter = takeDirectorySnapshot(tempMountDir);

            // Invariant: The filesystem state must be completely identical
            assertEquals(snapshotBefore, snapshotAfter, "Filesystem snapshot changed! Adapter must be strictly read-only.");
            assertFalse(Files.exists(tempMountDir.resolve("non_existent_folder")),
                    "Non-existent folder must never be created by adapter");
            assertFalse(Files.exists(tempMountDir.resolve("ghost_directory")),
                    "Ghost directory must never be created by adapter");
        }

        private Set<Path> takeDirectorySnapshot(Path dir) throws IOException {
            try (Stream<Path> stream = Files.walk(dir)) {
                return stream.collect(Collectors.toSet());
            }
        }
    }
}
