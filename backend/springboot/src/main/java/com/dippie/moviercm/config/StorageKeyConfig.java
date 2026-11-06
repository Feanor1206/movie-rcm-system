package com.dippie.moviercm.config;

import com.dippie.moviercm.exception.SecurityPathTraversalException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Server-side storage key allowlist and path containment resolver (C2).
 * Strictly maps incoming storage_key to configured server storage roots.
 */
@Component
public class StorageKeyConfig {

    public record StorageRoot(String provider, Path rootPath) {}

    private final Map<String, StorageRoot> allowlist = new ConcurrentHashMap<>();

    public StorageKeyConfig(
            @Value("${app.media.root:./media}") String localMediaRoot,
            @Value("${app.media.drive.mount-path:X:}") String driveMountPath
    ) {
        Path localPath = Paths.get(localMediaRoot).toAbsolutePath().normalize();
        Path drivePath;
        try {
            String sanitizedDrive = (driveMountPath != null && driveMountPath.endsWith(":"))
                    ? driveMountPath + java.io.File.separator
                    : (driveMountPath != null ? driveMountPath : "X:" + java.io.File.separator);
            drivePath = Paths.get(sanitizedDrive).toAbsolutePath().normalize();
        } catch (Throwable t) {
            drivePath = localPath.resolve("drive_mount").normalize();
        }

        // Standard registered storage keys
        allowlist.put("local_main", new StorageRoot("local", localPath));
        allowlist.put("local_storage", new StorageRoot("local", localPath));
        allowlist.put("drive_primary", new StorageRoot("drive", drivePath));
        allowlist.put("drive_storage", new StorageRoot("drive", drivePath));
        allowlist.put("google_drive", new StorageRoot("drive", drivePath));
        allowlist.put("drive_main", new StorageRoot("drive", drivePath));
        // Test fixture roots
        allowlist.put("demo_local", new StorageRoot("local", localPath.resolve("demo").normalize()));
        allowlist.put("test_drive", new StorageRoot("drive", localPath.resolve("test_drive").normalize()));
        allowlist.put("cinema-drive", new StorageRoot("drive", drivePath));
        allowlist.put("cinema_drive", new StorageRoot("drive", drivePath));
        allowlist.put("animation_drive", new StorageRoot("drive", drivePath));
        allowlist.put("animation_local", new StorageRoot("local", localPath));
    }

    public boolean isAllowed(String provider, String storageKey) {
        if (storageKey == null || provider == null) return false;
        StorageRoot root = allowlist.get(storageKey.toLowerCase());
        if (root == null) return false;
        String p = provider.equalsIgnoreCase("google_drive") ? "drive" : provider.toLowerCase();
        return root.provider().equalsIgnoreCase(p);
    }

    public StorageRoot getRoot(String provider, String storageKey) {
        if (storageKey == null) {
            throw new IllegalArgumentException("storage_key không được để trống");
        }
        StorageRoot root = allowlist.get(storageKey.toLowerCase());
        if (root == null) {
            throw new IllegalArgumentException("storage_key '" + storageKey + "' không nằm trong server allowlist");
        }
        String p = provider != null && provider.equalsIgnoreCase("google_drive") ? "drive" : (provider != null ? provider.toLowerCase() : "");
        if (!root.provider().equalsIgnoreCase(p)) {
            throw new IllegalArgumentException("Provider mismatch: storage_key '" + storageKey + "' yêu cầu provider " + root.provider() + " nhưng nhận được " + provider);
        }
        return root;
    }

    public Path resolvePath(String provider, String storageKey, String relativePath) {
        StorageRoot root = getRoot(provider, storageKey);
        if (relativePath == null || relativePath.trim().isEmpty()) {
            throw new SecurityPathTraversalException("Đường dẫn relative_path không được để trống");
        }
        if (relativePath.contains("\0") || relativePath.contains("..")) {
            throw new SecurityPathTraversalException("Phát hiện ký tự không hợp lệ hoặc path traversal");
        }

        Path resolved = root.rootPath().resolve(relativePath).normalize().toAbsolutePath();

        // Strict containment check
        if (!resolved.startsWith(root.rootPath())) {
            throw new SecurityPathTraversalException("Đường dẫn giải quyết vượt ra ngoài storage root cho phép: " + storageKey);
        }

        // Ancestor symlink / junction containment verification (G5, H4)
        // Only perform blocking disk checks on local storage; Drive disk I/O is bounded inside DriveMediaStorageAdapter
        if (!"drive".equalsIgnoreCase(root.provider()) && Files.exists(resolved)) {
            try {
                Path realTarget = resolved.toRealPath();
                Path realRoot = root.rootPath().toRealPath();
                if (!realTarget.startsWith(realRoot)) {
                    throw new SecurityPathTraversalException("Phát hiện liên kết tượng trưng (hoặc ancestor symlink/junction) trỏ ra ngoài storage root: " + storageKey);
                }
            } catch (IOException e) {
                throw new SecurityPathTraversalException("Không thể xác minh tính an toàn của đường dẫn: " + e.getMessage());
            }
        }

        return resolved;
    }

    public void registerKey(String key, String provider, Path path) {
        allowlist.put(key.toLowerCase(), new StorageRoot(provider.toLowerCase(), path.toAbsolutePath().normalize()));
    }
}
