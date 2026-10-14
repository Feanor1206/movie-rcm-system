package com.dippie.moviercm.service;

import com.dippie.moviercm.exception.MediaNotFoundException;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.exception.SecurityPathTraversalException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

@Component("localStorageAdapter")
public class LocalMediaStorageAdapter implements MediaStorageAdapter {

    private final String mediaRootConfig;

    public LocalMediaStorageAdapter(@Value("${app.media.root:./media}") String mediaRootConfig) {
        this.mediaRootConfig = mediaRootConfig;
    }

    @Override
    public String getProviderName() {
        return "local";
    }

    @Override
    public boolean isAvailable() {
        try {
            Path root = getNormalizedRoot();
            return Files.exists(root) && Files.isDirectory(root) && Files.isReadable(root);
        } catch (Exception e) {
            return false;
        }
    }

    public Path getNormalizedRoot() {
        return Paths.get(mediaRootConfig).toAbsolutePath().normalize();
    }

    @Override
    public Path resolveValidatedPath(String relativePath) {
        if (relativePath == null || relativePath.trim().isEmpty()) {
            throw new SecurityPathTraversalException("Đường dẫn media không được để trống");
        }

        // Check for null bytes
        if (relativePath.contains("\0")) {
            throw new SecurityPathTraversalException("Phát hiện ký tự null byte không hợp lệ");
        }

        // Check for path traversal patterns
        if (relativePath.contains("..")) {
            throw new SecurityPathTraversalException("Phát hiện đường dẫn vượt cấp (path traversal)");
        }

        // Check for Windows drive letters or absolute paths
        if (relativePath.matches("^[a-zA-Z]:.*") || relativePath.startsWith("/") || relativePath.startsWith("\\")) {
            throw new SecurityPathTraversalException("Đường dẫn media phải là đường dẫn tương đối bên dưới thư mục gốc");
        }

        Path root = getNormalizedRoot();
        if (!Files.exists(root) || !Files.isDirectory(root) || !Files.isReadable(root)) {
            throw new MediaUnavailableException("Thư mục lưu trữ media cục bộ không sẵn sàng hoặc không đọc được: " + root);
        }

        Path resolved = root.resolve(relativePath).normalize();

        // Enforce strict containment within root
        if (!resolved.startsWith(root)) {
            throw new SecurityPathTraversalException("Đường dẫn giải quyết nằm ngoài thư mục lưu trữ media hợp lệ");
        }

        if (!Files.exists(resolved) || !Files.isRegularFile(resolved)) {
            throw new MediaNotFoundException("Không tìm thấy tệp media trên hệ thống lưu trữ: " + relativePath);
        }

        try {
            Path realRoot = root.toRealPath();
            Path realTarget = resolved.toRealPath();
            if (!realTarget.startsWith(realRoot)) {
                throw new SecurityPathTraversalException("Phát hiện liên kết tượng trưng (symlink) trỏ ra ngoài media root");
            }
            return realTarget;
        } catch (IOException e) {
            throw new MediaNotFoundException("Không thể đọc tệp media hợp lệ: " + relativePath);
        }
    }

    @Override
    public Resource getResource(String relativePath) {
        Path targetPath = resolveValidatedPath(relativePath);
        Resource resource = new FileSystemResource(targetPath);
        if (!resource.exists() || !resource.isReadable()) {
            throw new MediaUnavailableException("Không thể mở luồng đọc cho tệp media: " + relativePath);
        }
        return resource;
    }

    @Override
    public long getResourceLength(String relativePath) {
        Path targetPath = resolveValidatedPath(relativePath);
        try {
            return Files.size(targetPath);
        } catch (IOException e) {
            throw new MediaUnavailableException("Không thể xác định kích thước tệp media: " + relativePath);
        }
    }
}
