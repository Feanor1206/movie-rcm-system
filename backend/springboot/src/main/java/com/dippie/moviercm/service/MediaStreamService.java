package com.dippie.moviercm.service;

import com.dippie.moviercm.config.StorageKeyConfig;
import com.dippie.moviercm.dto.MediaAssetDto;
import com.dippie.moviercm.dto.MediaDescriptorResponse;
import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.exception.InvalidMediaRangeException;
import com.dippie.moviercm.exception.MediaNotFoundException;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.repository.catalog.CatalogMediaAssetRepository;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.ResourceRegion;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

@Service
public class MediaStreamService {

    private final MovieRepository movieRepository;
    private final MediaAssetRepository mediaAssetRepository;
    private final LocalMediaStorageAdapter localStorageAdapter;
    private final DriveMediaStorageAdapter driveStorageAdapter;
    private final StorageKeyConfig storageKeyConfig;
    private final CatalogMediaAssetRepository catalogMediaAssetRepository;

    // Local stream bulkhead permits
    private final AtomicInteger activeStreamCount = new AtomicInteger(0);
    private final AtomicLong totalRejectedCount = new AtomicLong(0);
    private volatile int maxConcurrentStreams;

    // Drive stream bulkhead permits (strictly isolated from local)
    private final AtomicInteger activeDriveStreamCount = new AtomicInteger(0);
    private final AtomicLong totalDriveRejectedCount = new AtomicLong(0);
    private volatile int maxConcurrentDriveStreams;

    private static volatile java.util.concurrent.CountDownLatch testStreamGate = null;

    public static void setTestStreamGate(java.util.concurrent.CountDownLatch gate) {
        testStreamGate = gate;
    }

    public static java.util.concurrent.CountDownLatch getTestStreamGate() {
        return testStreamGate;
    }

    public static void awaitTestStreamGate(long timeoutMs) {
        java.util.concurrent.CountDownLatch gate = testStreamGate;
        if (gate != null) {
            try {
                gate.await(timeoutMs, java.util.concurrent.TimeUnit.MILLISECONDS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    @Autowired
    public MediaStreamService(MovieRepository movieRepository,
                              MediaAssetRepository mediaAssetRepository,
                              LocalMediaStorageAdapter localStorageAdapter,
                              DriveMediaStorageAdapter driveStorageAdapter,
                              @Autowired(required = false) StorageKeyConfig storageKeyConfig,
                              @Autowired(required = false) CatalogMediaAssetRepository catalogMediaAssetRepository,
                              @Value("${app.media.max-concurrent-streams:10}") int maxConcurrentStreams,
                              @Value("${app.media.max-concurrent-drive-streams:5}") int maxConcurrentDriveStreams) {
        this.movieRepository = movieRepository;
        this.mediaAssetRepository = mediaAssetRepository;
        this.localStorageAdapter = localStorageAdapter;
        this.driveStorageAdapter = driveStorageAdapter;
        this.storageKeyConfig = storageKeyConfig;
        this.catalogMediaAssetRepository = catalogMediaAssetRepository;
        this.maxConcurrentStreams = maxConcurrentStreams > 0 ? maxConcurrentStreams : 10;
        this.maxConcurrentDriveStreams = maxConcurrentDriveStreams > 0 ? maxConcurrentDriveStreams : 5;
    }

    public MediaStreamService(MovieRepository movieRepository,
                              MediaAssetRepository mediaAssetRepository,
                              LocalMediaStorageAdapter localStorageAdapter,
                              DriveMediaStorageAdapter driveStorageAdapter,
                              int maxConcurrentStreams,
                              int maxConcurrentDriveStreams) {
        this(movieRepository, mediaAssetRepository, localStorageAdapter, driveStorageAdapter, null, null, maxConcurrentStreams, maxConcurrentDriveStreams);
    }

    public MediaStreamService(MovieRepository movieRepository,
                              MediaAssetRepository mediaAssetRepository,
                              LocalMediaStorageAdapter localStorageAdapter,
                              DriveMediaStorageAdapter driveStorageAdapter,
                              int maxConcurrentStreams) {
        this(movieRepository, mediaAssetRepository, localStorageAdapter, driveStorageAdapter, null, null, maxConcurrentStreams, 5);
    }

    public MediaStreamService(MovieRepository movieRepository,
                              MediaAssetRepository mediaAssetRepository,
                              LocalMediaStorageAdapter localStorageAdapter,
                              DriveMediaStorageAdapter driveStorageAdapter) {
        this(movieRepository, mediaAssetRepository, localStorageAdapter, driveStorageAdapter, null, null, 10, 5);
    }

    // --- Bulkhead Permit Management: Local ---

    public boolean acquireStreamPermit() {
        int current = activeStreamCount.incrementAndGet();
        if (current > maxConcurrentStreams) {
            activeStreamCount.decrementAndGet();
            totalRejectedCount.incrementAndGet();
            return false;
        }
        return true;
    }

    public void releaseStreamPermit() {
        activeStreamCount.updateAndGet(c -> Math.max(0, c - 1));
    }

    public int getActiveStreamCount() {
        return activeStreamCount.get();
    }

    public long getTotalRejectedCount() {
        return totalRejectedCount.get();
    }

    public int getMaxConcurrentStreams() {
        return maxConcurrentStreams;
    }

    public void setMaxConcurrentStreams(int maxConcurrentStreams) {
        this.maxConcurrentStreams = maxConcurrentStreams > 0 ? maxConcurrentStreams : 10;
    }

    // --- Bulkhead Permit Management: Drive ---

    public boolean acquireDriveStreamPermit() {
        int current = activeDriveStreamCount.incrementAndGet();
        if (current > maxConcurrentDriveStreams) {
            activeDriveStreamCount.decrementAndGet();
            totalDriveRejectedCount.incrementAndGet();
            return false;
        }
        return true;
    }

    public void releaseDriveStreamPermit() {
        activeDriveStreamCount.updateAndGet(c -> Math.max(0, c - 1));
    }

    public int getDriveActiveStreamCount() {
        return activeDriveStreamCount.get();
    }

    public int getActiveDriveStreamCount() {
        return activeDriveStreamCount.get();
    }

    public long getTotalDriveRejectedCount() {
        return totalDriveRejectedCount.get();
    }

    public int getMaxConcurrentDriveStreams() {
        return maxConcurrentDriveStreams;
    }

    public void setMaxConcurrentDriveStreams(int maxConcurrentDriveStreams) {
        this.maxConcurrentDriveStreams = maxConcurrentDriveStreams > 0 ? maxConcurrentDriveStreams : 5;
    }

    // --- Unified Bulkhead Dispatch ---

    public boolean acquireStreamPermit(MediaAsset asset) {
        if (asset != null && "drive".equalsIgnoreCase(asset.getStorageProvider())) {
            return acquireDriveStreamPermit();
        }
        return acquireStreamPermit();
    }

    public boolean acquireStreamPermit(String provider) {
        if ("drive".equalsIgnoreCase(provider)) {
            return acquireDriveStreamPermit();
        }
        return acquireStreamPermit();
    }

    public void releaseStreamPermit(MediaAsset asset) {
        if (asset != null && "drive".equalsIgnoreCase(asset.getStorageProvider())) {
            releaseDriveStreamPermit();
        } else {
            releaseStreamPermit();
        }
    }

    public void releaseStreamPermit(String provider) {
        if ("drive".equalsIgnoreCase(provider)) {
            releaseDriveStreamPermit();
        } else {
            releaseStreamPermit();
        }
    }

    // --- Descriptor & Asset Operations ---

    public MediaDescriptorResponse getMediaDescriptor(String movieId) {
        Movie movie = movieRepository.findById(movieId)
                .orElseThrow(() -> new MediaNotFoundException("Không tìm thấy phim với mã: " + movieId));

        List<MediaAsset> assets = mediaAssetRepository.findByMovieIdAndIsAvailableTrue(movieId).stream()
                .filter(a -> Boolean.TRUE.equals(a.getPublic()))
                .toList();

        MediaAsset featureAsset = assets.stream()
                .filter(a -> "feature".equalsIgnoreCase(a.getKind()))
                .findFirst()
                .orElse(null);

        MediaAsset trailerAsset = assets.stream()
                .filter(a -> "trailer".equalsIgnoreCase(a.getKind()))
                .findFirst()
                .orElse(null);

        if (featureAsset != null && "drive".equalsIgnoreCase(featureAsset.getStorageProvider()) && !driveStorageAdapter.isAvailable()) {
            throw new MediaUnavailableException("Kho lưu trữ Google Drive hiện không sẵn sàng (mount offline)");
        }

        MediaAssetDto featureDto = featureAsset != null ? toDto(featureAsset) : null;
        MediaAssetDto trailerDto = null;

        if (trailerAsset != null) {
            if ("drive".equalsIgnoreCase(trailerAsset.getStorageProvider()) && !driveStorageAdapter.isAvailable()) {
                throw new MediaUnavailableException("Kho lưu trữ Google Drive hiện không sẵn sàng (mount offline)");
            }
            trailerDto = toDto(trailerAsset);
        } else if (movie.getVideoUrl() != null && !movie.getVideoUrl().trim().isEmpty()) {
            // Backward-compatible fallback trailer
            trailerDto = new MediaAssetDto(
                    "fallback-trailer-" + movie.getId(),
                    "trailer",
                    movie.getVideoUrl(),
                    "video/mp4",
                    0L,
                    null,
                    true,
                    "legacy"
            );
        }

        return new MediaDescriptorResponse(
                movie.getId(),
                featureDto != null,
                trailerDto != null,
                featureDto,
                trailerDto
        );
    }

    public MediaAsset getMediaAsset(String assetId) {
        MediaAsset asset = mediaAssetRepository.findByIdAndIsAvailableTrue(assetId)
                .orElseThrow(() -> new MediaNotFoundException("Không tìm thấy tài nguyên media: " + assetId));
        if (Boolean.TRUE.equals(asset.getPublic())) {
            return asset;
        }

        // Allow playback for non-public assets if user is authenticated (and admin if private)
        org.springframework.security.core.Authentication auth =
                org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
        boolean isAuthenticated = auth != null && auth.isAuthenticated()
                && !(auth instanceof org.springframework.security.authentication.AnonymousAuthenticationToken);

        if (!isAuthenticated) {
            throw new MediaNotFoundException("Không tìm thấy tài nguyên media: " + assetId);
        }

        if (catalogMediaAssetRepository != null) {
            Optional<com.dippie.moviercm.entity.catalog.CatalogMediaAsset> cAsset = catalogMediaAssetRepository.findById(assetId);
            if (cAsset.isPresent() && "private".equalsIgnoreCase(cAsset.get().getAccessPolicy())) {
                boolean isAdmin = auth.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));
                if (!isAdmin) {
                    throw new MediaNotFoundException("Không tìm thấy tài nguyên media: " + assetId);
                }
            }
        }
        return asset;
    }

    public MediaStorageAdapter getStorageAdapter(String providerName) {
        if ("drive".equalsIgnoreCase(providerName)) {
            return driveStorageAdapter;
        }
        if ("local".equalsIgnoreCase(providerName)) {
            return localStorageAdapter;
        }
        throw new MediaUnavailableException("Storage provider không được hỗ trợ: " + providerName);
    }

    public Resource getMediaResource(MediaAsset asset) {
        if (storageKeyConfig != null && asset.getStorageKey() != null && !asset.getStorageKey().isBlank()) {
            StorageKeyConfig.StorageRoot root = storageKeyConfig.getRoot(asset.getStorageProvider(), asset.getStorageKey());
            java.nio.file.Path targetPath = storageKeyConfig.resolvePath(asset.getStorageProvider(), asset.getStorageKey(), asset.getRelativePath());
            if ("drive".equalsIgnoreCase(asset.getStorageProvider()) && driveStorageAdapter != null) {
                return driveStorageAdapter.getResourceForPath(root.rootPath(), targetPath);
            }
            Resource resource = new org.springframework.core.io.FileSystemResource(targetPath);
            if (!resource.exists() || !resource.isReadable()) {
                throw new MediaUnavailableException("Không thể mở luồng đọc cho tệp media: " + asset.getRelativePath());
            }
            return resource;
        }
        MediaStorageAdapter adapter = getStorageAdapter(asset.getStorageProvider());
        return adapter.getResource(asset.getRelativePath());
    }

    public long getResourceLength(MediaAsset asset) {
        if (storageKeyConfig != null && asset.getStorageKey() != null && !asset.getStorageKey().isBlank()) {
            StorageKeyConfig.StorageRoot root = storageKeyConfig.getRoot(asset.getStorageProvider(), asset.getStorageKey());
            java.nio.file.Path targetPath = storageKeyConfig.resolvePath(asset.getStorageProvider(), asset.getStorageKey(), asset.getRelativePath());
            if ("drive".equalsIgnoreCase(asset.getStorageProvider()) && driveStorageAdapter != null) {
                return driveStorageAdapter.getResourceLengthForPath(root.rootPath(), targetPath);
            }
            try {
                return java.nio.file.Files.size(targetPath);
            } catch (IOException e) {
                throw new MediaUnavailableException("Không thể xác định kích thước tệp media: " + asset.getRelativePath());
            }
        }
        MediaStorageAdapter adapter = getStorageAdapter(asset.getStorageProvider());
        return adapter.getResourceLength(asset.getRelativePath());
    }

    public java.nio.channels.SeekableByteChannel openMediaChannel(MediaAsset asset) throws IOException {
        if (storageKeyConfig != null && asset.getStorageKey() != null && !asset.getStorageKey().isBlank()) {
            StorageKeyConfig.StorageRoot root = storageKeyConfig.getRoot(asset.getStorageProvider(), asset.getStorageKey());
            java.nio.file.Path targetPath = storageKeyConfig.resolvePath(asset.getStorageProvider(), asset.getStorageKey(), asset.getRelativePath());
            if ("drive".equalsIgnoreCase(asset.getStorageProvider()) && driveStorageAdapter != null) {
                return driveStorageAdapter.openChannelForPath(root.rootPath(), targetPath);
            }
            if (!java.nio.file.Files.exists(targetPath) || !java.nio.file.Files.isRegularFile(targetPath)) {
                throw new MediaNotFoundException("Không tìm thấy tệp media: " + asset.getRelativePath());
            }
            return java.nio.channels.FileChannel.open(targetPath, java.nio.file.StandardOpenOption.READ);
        }
        MediaStorageAdapter adapter = getStorageAdapter(asset.getStorageProvider());
        return adapter.openChannel(asset.getRelativePath());
    }

    public RangeSpec parseRange(String rangeHeader, long totalLength) {
        if (rangeHeader == null || rangeHeader.trim().isEmpty()) {
            return new RangeSpec(0, totalLength - 1, totalLength, false);
        }

        String trimmed = rangeHeader.trim();
        if (!trimmed.startsWith("bytes=")) {
            throw new InvalidMediaRangeException("Tiêu đề Range phải bắt đầu bằng 'bytes='", totalLength);
        }

        String spec = trimmed.substring(6).trim();

        try {
            if (spec.startsWith("-")) {
                // Suffix range: bytes=-500
                long suffix = Long.parseLong(spec.substring(1));
                if (suffix <= 0) {
                    throw new InvalidMediaRangeException("Độ dài suffix phải lớn hơn 0", totalLength);
                }
                long start = Math.max(0, totalLength - suffix);
                long end = totalLength - 1;
                return new RangeSpec(start, end, totalLength, true);
            }

            int dashIndex = spec.indexOf('-');
            if (dashIndex == -1) {
                throw new InvalidMediaRangeException("Định dạng Range thiếu dấu gạch nối", totalLength);
            }

            long start = Long.parseLong(spec.substring(0, dashIndex).trim());
            if (start < 0 || start >= totalLength) {
                throw new InvalidMediaRangeException("Vị trí bắt đầu Range nằm ngoài kích thước tệp", totalLength);
            }

            String endPart = spec.substring(dashIndex + 1).trim();
            long end;
            if (endPart.isEmpty()) {
                // Open-ended range: bytes=1024-
                end = totalLength - 1;
            } else {
                // Closed range: bytes=0-1023
                end = Long.parseLong(endPart);
                if (start > end) {
                    throw new InvalidMediaRangeException("Vị trí bắt đầu Range không được lớn hơn vị trí kết thúc", totalLength);
                }
                if (end >= totalLength) {
                    end = totalLength - 1;
                }
            }

            return new RangeSpec(start, end, totalLength, true);
        } catch (NumberFormatException e) {
            throw new InvalidMediaRangeException("Giá trị Range không phải là số hợp lệ", totalLength);
        }
    }

    public ResourceRegion createResourceRegion(Resource resource, RangeSpec range) {
        long position = range.getStart();
        long count = range.getLength();
        return new ResourceRegion(resource, position, count);
    }

    private MediaAssetDto toDto(MediaAsset asset) {
        return new MediaAssetDto(
                asset.getId(),
                asset.getKind(),
                "/api/media/stream/" + asset.getId(),
                asset.getMimeType(),
                asset.getByteLength(),
                asset.getDurationSeconds(),
                asset.getPublic(),
                asset.getVersion()
        );
    }

    public static class RangeSpec {
        private final long start;
        private final long end;
        private final long total;
        private final boolean isRanged;

        public RangeSpec(long start, long end, long total, boolean isRanged) {
            this.start = start;
            this.end = end;
            this.total = total;
            this.isRanged = isRanged;
        }

        public long getStart() {
            return start;
        }

        public long getEnd() {
            return end;
        }

        public long getLength() {
            return end - start + 1;
        }

        public long getTotal() {
            return total;
        }

        public boolean isRanged() {
            return isRanged;
        }
    }
}
