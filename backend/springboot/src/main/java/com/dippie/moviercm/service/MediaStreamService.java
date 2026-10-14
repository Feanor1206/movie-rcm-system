package com.dippie.moviercm.service;

import com.dippie.moviercm.dto.MediaAssetDto;
import com.dippie.moviercm.dto.MediaDescriptorResponse;
import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.exception.InvalidMediaRangeException;
import com.dippie.moviercm.exception.MediaNotFoundException;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.ResourceRegion;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

@Service
public class MediaStreamService {

    private final MovieRepository movieRepository;
    private final MediaAssetRepository mediaAssetRepository;
    private final LocalMediaStorageAdapter localStorageAdapter;
    private final DriveMediaStorageAdapter driveStorageAdapter;

    private final AtomicInteger activeStreamCount = new AtomicInteger(0);
    private final AtomicLong totalRejectedCount = new AtomicLong(0);
    private volatile int maxConcurrentStreams;

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
                              @Value("${app.media.max-concurrent-streams:10}") int maxConcurrentStreams) {
        this.movieRepository = movieRepository;
        this.mediaAssetRepository = mediaAssetRepository;
        this.localStorageAdapter = localStorageAdapter;
        this.driveStorageAdapter = driveStorageAdapter;
        this.maxConcurrentStreams = maxConcurrentStreams > 0 ? maxConcurrentStreams : 10;
    }

    public MediaStreamService(MovieRepository movieRepository,
                              MediaAssetRepository mediaAssetRepository,
                              LocalMediaStorageAdapter localStorageAdapter,
                              DriveMediaStorageAdapter driveStorageAdapter) {
        this(movieRepository, mediaAssetRepository, localStorageAdapter, driveStorageAdapter, 10);
    }

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
        if (!Boolean.TRUE.equals(asset.getPublic())) {
            throw new MediaNotFoundException("Không tìm thấy tài nguyên media: " + assetId);
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
        MediaStorageAdapter adapter = getStorageAdapter(asset.getStorageProvider());
        return adapter.getResource(asset.getRelativePath());
    }

    public long getResourceLength(MediaAsset asset) {
        MediaStorageAdapter adapter = getStorageAdapter(asset.getStorageProvider());
        return adapter.getResourceLength(asset.getRelativePath());
    }

    public java.nio.channels.SeekableByteChannel openMediaChannel(MediaAsset asset) throws IOException {
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
