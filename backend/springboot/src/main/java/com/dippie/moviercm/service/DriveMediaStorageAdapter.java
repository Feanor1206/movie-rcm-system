package com.dippie.moviercm.service;

import com.dippie.moviercm.exception.MediaNotFoundException;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.exception.SecurityPathTraversalException;
import com.dippie.moviercm.service.storage.DriveCircuitBreaker;
import com.dippie.moviercm.service.storage.DriveIoExecutor;
import com.dippie.moviercm.service.storage.DriveResourceReservation;
import com.dippie.moviercm.service.storage.DriveSeekableByteChannel;
import org.springframework.beans.factory.annotation.Autowired;
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
    private final long metadataTimeoutMs;
    private final long readTimeoutMs;
    private final int maxIoWorkers;
    private final DriveIoExecutor ioExecutor;

    @Autowired
    public DriveMediaStorageAdapter(
            @Value("${app.media.drive-mount:}") String driveMountPath,
            @Value("${app.media.drive-metadata-timeout-ms:3000}") long metadataTimeoutMs,
            @Value("${app.media.drive-read-timeout-ms:5000}") long readTimeoutMs,
            @Value("${app.media.drive-max-io-workers:10}") int maxIoWorkers,
            @Value("${app.media.drive-circuit-failure-threshold:5}") int circuitFailureThreshold,
            @Value("${app.media.drive-circuit-cooldown-ms:10000}") long circuitCooldownMs) {
        this.driveMountPath = driveMountPath;
        this.metadataTimeoutMs = metadataTimeoutMs > 0 ? metadataTimeoutMs : 3000;
        this.readTimeoutMs = readTimeoutMs > 0 ? readTimeoutMs : 5000;
        this.maxIoWorkers = maxIoWorkers > 0 ? maxIoWorkers : 10;
        this.ioExecutor = new DriveIoExecutor(
                this.metadataTimeoutMs,
                this.readTimeoutMs,
                this.maxIoWorkers,
                new DriveCircuitBreaker(circuitFailureThreshold, circuitCooldownMs)
        );
    }

    public DriveMediaStorageAdapter(String driveMountPath) {
        this(driveMountPath, 3000, 5000, 10, 5, 10000);
    }

    public DriveMediaStorageAdapter(String driveMountPath, DriveIoExecutor ioExecutor) {
        this.driveMountPath = driveMountPath;
        this.metadataTimeoutMs = ioExecutor.getMetadataTimeoutMs();
        this.readTimeoutMs = ioExecutor.getReadTimeoutMs();
        this.maxIoWorkers = ioExecutor.getMaxWorkers();
        this.ioExecutor = ioExecutor;
    }

    @Override
    public String getProviderName() {
        return "drive";
    }

    public int getOutstandingWorkerCount() {
        return ioExecutor.getActualOutstandingWorkers();
    }

    public DriveIoExecutor getIoExecutor() {
        return ioExecutor;
    }

    public DriveCircuitBreaker getCircuitBreaker() {
        return ioExecutor.getCircuitBreaker();
    }

    @Override
    public boolean isAvailable() {
        if (driveMountPath == null || driveMountPath.trim().isEmpty()) {
            return false;
        }
        if (!ioExecutor.getCircuitBreaker().allowExecution()) {
            return false;
        }
        if (ioExecutor.getActualOutstandingWorkers() >= maxIoWorkers) {
            return false;
        }
        try {
            return ioExecutor.executeMetadata(() -> {
                Path root = Paths.get(driveMountPath).toAbsolutePath().normalize();
                return Files.exists(root) && Files.isDirectory(root) && (root.toFile().canRead() || Files.isReadable(root));
            });
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
                    "Thư mục mount Google Drive không sẵn sàng hoặc không đọc được"
            );
        }

        return ioExecutor.executeMetadata(() -> {
            Path root;
            try {
                root = Paths.get(driveMountPath).toAbsolutePath().normalize();
            } catch (Exception e) {
                throw new MediaUnavailableException(
                        "Thư mục mount Google Drive không sẵn sàng hoặc không đọc được"
                );
            }

            if (!Files.exists(root) || !Files.isDirectory(root) || (!root.toFile().canRead() && !Files.isReadable(root))) {
                throw new MediaUnavailableException(
                        "Thư mục mount Google Drive không sẵn sàng hoặc không đọc được"
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

            if ((!resolved.toFile().canRead() && !Files.isReadable(resolved))
                    || (!realTarget.toFile().canRead() && !Files.isReadable(realTarget))) {
                throw new MediaUnavailableException(
                        "Tệp media trên Google Drive không có quyền đọc: " + relativePath
                );
            }

            return realTarget;
        });
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
        return ioExecutor.executeMetadata(() -> {
            try {
                return Files.size(targetPath);
            } catch (IOException e) {
                throw new MediaUnavailableException("Không thể xác định kích thước tệp media: " + relativePath);
            }
        });
    }

    @Override
    public SeekableByteChannel openChannel(String relativePath) throws IOException {
        Path targetPath = resolveValidatedPath(relativePath);
        return openChannelForPath(targetPath);
    }

    public Resource getResourceForPath(Path targetPath) {
        Resource resource = new FileSystemResource(targetPath);
        if (!resource.exists() || !resource.isReadable()) {
            throw new MediaUnavailableException("Không thể mở luồng đọc cho tệp media: " + targetPath);
        }
        return resource;
    }

    public long getResourceLengthForPath(Path targetPath) {
        return ioExecutor.executeMetadata(() -> {
            try {
                return Files.size(targetPath);
            } catch (IOException e) {
                throw new MediaUnavailableException("Không thể xác định kích thước tệp media: " + targetPath);
            }
        });
    }

    public SeekableByteChannel openChannelForPath(Path targetPath) throws IOException {
        if (!Files.exists(targetPath) || !Files.isRegularFile(targetPath)) {
            throw new MediaNotFoundException("Không tìm thấy tệp media trên Google Drive: " + targetPath);
        }
        DriveResourceReservation reservation = ioExecutor.acquireReservation();
        try {
            FileChannel rawChannel = ioExecutor.executeOpen(
                    () -> FileChannel.open(targetPath, StandardOpenOption.READ),
                    ioExecutor.getMetadataTimeoutMs(),
                    "openChannel:" + targetPath.getFileName(),
                    reservation
            );
            return new DriveSeekableByteChannel(rawChannel, ioExecutor, reservation);
        } catch (Throwable t) {
            throw t;
        }
    }
}
