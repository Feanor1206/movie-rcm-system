package com.dippie.moviercm.service;

import com.dippie.moviercm.exception.MediaNotFoundException;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.exception.SecurityPathTraversalException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;

@Component("driveStorageAdapter")
public class DriveMediaStorageAdapter implements MediaStorageAdapter {

    private final String driveMountPath;

    public DriveMediaStorageAdapter(@Value("${app.media.drive-mount:}") String driveMountPath) {
        this.driveMountPath = driveMountPath;
    }

    @Override
    public String getProviderName() {
        return "drive";
    }

    @Override
    public boolean isAvailable() {
        if (driveMountPath == null || driveMountPath.trim().isEmpty()) {
            return false;
        }
        try {
            Path root = Paths.get(driveMountPath).toAbsolutePath().normalize();
            return Files.exists(root) && Files.isDirectory(root) && Files.isReadable(root);
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    public Path resolveValidatedPath(String relativePath) {
        if (relativePath == null || relativePath.trim().isEmpty()) {
            throw new SecurityPathTraversalException("Đường dẫn media không được để trống");
        }

        if (relativePath.contains("\0")) {
            throw new SecurityPathTraversalException("Phát hiện ký tự null byte không hợp lệ");
        }

        if (relativePath.contains("..")) {
            throw new SecurityPathTraversalException("Phát hiện đường dẫn vượt cấp (path traversal)");
        }

        if (relativePath.matches("^[a-zA-Z]:.*")
                || relativePath.startsWith("/")
                || relativePath.startsWith("\\")) {
            throw new SecurityPathTraversalException(
                    "Đường dẫn media phải là đường dẫn tương đối bên dưới thư mục gốc mount Google Drive"
            );
        }

        if (driveMountPath == null || driveMountPath.trim().isEmpty()) {
            throw new MediaUnavailableException(
                    "Thư mục mount Google Drive không sẵn sàng hoặc không đọc được: " + driveMountPath
            );
        }

        Path root;
        try {
            root = Paths.get(driveMountPath).toAbsolutePath().normalize();
        } catch (Exception e) {
            throw new MediaUnavailableException(
                    "Thư mục mount Google Drive không sẵn sàng hoặc không đọc được: " + driveMountPath
            );
        }

        if (!Files.exists(root) || !Files.isDirectory(root) || !Files.isReadable(root)) {
            throw new MediaUnavailableException(
                    "Thư mục mount Google Drive không sẵn sàng hoặc không đọc được: " + driveMountPath
            );
        }

        Path resolved = root.resolve(relativePath).normalize();

        if (!resolved.startsWith(root)) {
            throw new SecurityPathTraversalException("Đường dẫn giải quyết nằm ngoài thư mục lưu trữ media hợp lệ");
        }

        if (!Files.exists(resolved) || !Files.isRegularFile(resolved)) {
            if (Files.isSymbolicLink(resolved)) {
                try {
                    Path linkTarget = Files.readSymbolicLink(resolved);
                    Path normalizedTarget = resolved.getParent() != null
                            ? resolved.getParent().resolve(linkTarget).normalize()
                            : linkTarget.normalize();
                    if (!normalizedTarget.startsWith(root)) {
                        throw new SecurityPathTraversalException(
                                "Phát hiện liên kết tượng trưng (symlink) trỏ ra ngoài Drive root"
                        );
                    }
                } catch (SecurityPathTraversalException e) {
                    throw e;
                } catch (Exception ignored) {
                }
            }
            throw new MediaNotFoundException("Không tìm thấy tệp media trên Google Drive: " + relativePath);
        }

        Path realRoot;
        Path realTarget;
        try {
            realRoot = root.toRealPath();
            realTarget = resolved.toRealPath();
        } catch (IOException e) {
            throw new MediaNotFoundException("Không tìm thấy tệp media trên Google Drive: " + relativePath);
        }

        if (!realTarget.startsWith(realRoot)) {
            throw new SecurityPathTraversalException(
                    "Phát hiện liên kết tượng trưng (symlink) trỏ ra ngoài Drive root"
            );
        }

        if (!Files.isReadable(resolved) || !Files.isReadable(realTarget)) {
            throw new MediaUnavailableException(
                    "Tệp media trên Google Drive không có quyền đọc: " + relativePath
            );
        }

        return realTarget;
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

    @Override
    public SeekableByteChannel openChannel(String relativePath) throws IOException {
        Path targetPath = resolveValidatedPath(relativePath);
        return FileChannel.open(targetPath, StandardOpenOption.READ);
    }
}
