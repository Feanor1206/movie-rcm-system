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
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.List;

@Service
public class MediaStreamService {

    private final MovieRepository movieRepository;
    private final MediaAssetRepository mediaAssetRepository;
    private final LocalMediaStorageAdapter localStorageAdapter;
    private final DriveMediaStorageAdapter driveStorageAdapter;

    public MediaStreamService(MovieRepository movieRepository,
                              MediaAssetRepository mediaAssetRepository,
                              LocalMediaStorageAdapter localStorageAdapter,
                              DriveMediaStorageAdapter driveStorageAdapter) {
        this.movieRepository = movieRepository;
        this.mediaAssetRepository = mediaAssetRepository;
        this.localStorageAdapter = localStorageAdapter;
        this.driveStorageAdapter = driveStorageAdapter;
    }

    public MediaDescriptorResponse getMediaDescriptor(String movieId) {
        Movie movie = movieRepository.findById(movieId)
                .orElseThrow(() -> new MediaNotFoundException("Không tìm thấy phim với mã: " + movieId));

        List<MediaAsset> assets = mediaAssetRepository.findByMovieIdAndIsAvailableTrue(movieId);

        MediaAsset featureAsset = assets.stream()
                .filter(a -> "feature".equalsIgnoreCase(a.getKind()))
                .findFirst()
                .orElse(null);

        MediaAsset trailerAsset = assets.stream()
                .filter(a -> "trailer".equalsIgnoreCase(a.getKind()))
                .findFirst()
                .orElse(null);

        MediaAssetDto featureDto = featureAsset != null ? toDto(featureAsset) : null;
        MediaAssetDto trailerDto = null;

        if (trailerAsset != null) {
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
        return mediaAssetRepository.findByIdAndIsAvailableTrue(assetId)
                .orElseThrow(() -> new MediaNotFoundException("Không tìm thấy tài nguyên media: " + assetId));
    }

    public MediaStorageAdapter getStorageAdapter(String providerName) {
        if ("drive".equalsIgnoreCase(providerName)) {
            return driveStorageAdapter;
        }
        return localStorageAdapter;
    }

    public Resource getMediaResource(MediaAsset asset) {
        MediaStorageAdapter adapter = getStorageAdapter(asset.getStorageProvider());
        return adapter.getResource(asset.getRelativePath());
    }

    public long getResourceLength(MediaAsset asset) {
        MediaStorageAdapter adapter = getStorageAdapter(asset.getStorageProvider());
        return adapter.getResourceLength(asset.getRelativePath());
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
