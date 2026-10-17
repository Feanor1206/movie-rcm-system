package com.dippie.moviercm.controller;

import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.service.MediaStreamService;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.Resource;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

import com.dippie.moviercm.security.JwtUtils;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.authentication.AnonymousAuthenticationToken;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.util.Map;

@RestController
@RequestMapping("/api/media")
public class MediaStreamController {

    private static final Logger logger = LoggerFactory.getLogger(MediaStreamController.class);
    private static final int BUFFER_SIZE = 64 * 1024; // 64 KiB bounded buffer

    private final MediaStreamService mediaStreamService;
    private final JwtUtils jwtUtils;

    public MediaStreamController(MediaStreamService mediaStreamService) {
        this(mediaStreamService, null);
    }

    @org.springframework.beans.factory.annotation.Autowired
    public MediaStreamController(MediaStreamService mediaStreamService, @org.springframework.beans.factory.annotation.Autowired(required = false) JwtUtils jwtUtils) {
        this.mediaStreamService = mediaStreamService;
        this.jwtUtils = jwtUtils;
    }

    @PostMapping("/grant/{assetId}")
    public ResponseEntity<Map<String, Object>> requestPlaybackGrant(@PathVariable String assetId) {
        MediaAsset asset = mediaStreamService.getMediaAsset(assetId);
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        boolean isAuthenticated = auth != null && auth.isAuthenticated()
                && !(auth instanceof AnonymousAuthenticationToken);

        String username = isAuthenticated ? auth.getName() : "anonymous";
        String role = isAuthenticated
                ? auth.getAuthorities().stream().map(GrantedAuthority::getAuthority).findFirst().orElse("ROLE_USER")
                : "ROLE_ANONYMOUS";

        long validityMs = 300_000L; // 5 minutes (H4)
        String grantToken = jwtUtils.generatePlaybackGrant(assetId, username, role, validityMs);

        return ResponseEntity.ok(Map.of(
                "assetId", assetId,
                "grant", grantToken,
                "streamUrl", "/api/media/stream/" + assetId + "?grant=" + grantToken,
                "expiresIn", 300
        ));
    }

    @RequestMapping(value = "/stream/{assetId}", method = RequestMethod.HEAD)
    public ResponseEntity<Void> getStreamHeaders(@PathVariable String assetId) {
        MediaAsset asset = mediaStreamService.getMediaAsset(assetId);
        long length = mediaStreamService.getResourceLength(asset);

        CacheControl cacheControl = asset.isPublic()
                ? CacheControl.maxAge(3600, java.util.concurrent.TimeUnit.SECONDS).cachePublic()
                : CacheControl.noStore().noCache().mustRevalidate().cachePrivate();

        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(asset.getMimeType()))
                .contentLength(length)
                .header(HttpHeaders.ACCEPT_RANGES, "bytes")
                .eTag(asset.getId() + "-" + asset.getVersion())
                .cacheControl(cacheControl)
                .build();
    }

    @GetMapping("/stream/{assetId}")
    public void streamMedia(
            @PathVariable String assetId,
            @RequestHeader(value = HttpHeaders.RANGE, required = false) String rangeHeader,
            HttpServletResponse response) throws IOException {

        // 1. Resolve asset first (throws 404 MediaNotFoundException if not found, before acquiring permits)
        MediaAsset asset = mediaStreamService.getMediaAsset(assetId);

        // 2. Bulkhead isolation: acquire provider-specific stream permit
        if (!mediaStreamService.acquireStreamPermit(asset)) {
            response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
            response.setHeader(HttpHeaders.RETRY_AFTER, "5");
            response.setHeader(HttpHeaders.CACHE_CONTROL, "no-store, no-cache, must-revalidate");
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            response.getWriter().write("{\"status\":429,\"error\":\"Too Many Requests\",\"message\":\"Hệ thống đang phục vụ tối đa luồng phát media đồng thời. Vui lòng thử lại sau 5 giây.\"}");
            response.getWriter().flush();
            return;
        }

        try {
            MediaStreamService.awaitTestStreamGate(5000);
            long totalLength = mediaStreamService.getResourceLength(asset);
            MediaStreamService.RangeSpec range = mediaStreamService.parseRange(rangeHeader, totalLength);

            // Open channel BEFORE committing response or setting headers
            try (SeekableByteChannel channel = mediaStreamService.openMediaChannel(asset)) {

                response.setHeader(HttpHeaders.ACCEPT_RANGES, "bytes");
                response.setHeader(HttpHeaders.ETAG, "\"" + asset.getId() + "-" + asset.getVersion() + "\"");
                String cacheControlHeader = asset.isPublic()
                        ? "public, max-age=3600"
                        : "private, no-cache, no-store, must-revalidate";
                response.setHeader(HttpHeaders.CACHE_CONTROL, cacheControlHeader);
                response.setContentType(asset.getMimeType());

                if (!range.isRanged()) {
                    response.setStatus(HttpServletResponse.SC_OK);
                    response.setHeader(HttpHeaders.CONTENT_LENGTH, String.valueOf(totalLength));

                    try (OutputStream out = response.getOutputStream()) {
                        ByteBuffer buffer = ByteBuffer.allocate(BUFFER_SIZE);
                        long totalWritten = 0;
                        int bytesRead;
                        while ((bytesRead = channel.read(buffer)) != -1) {
                            buffer.flip();
                            out.write(buffer.array(), buffer.arrayOffset(), buffer.limit());
                            totalWritten += bytesRead;
                            buffer.clear();
                        }
                        if (totalWritten < totalLength) {
                            throw new IOException("Stream read truncated: expected " + totalLength + " bytes but got " + totalWritten);
                        }
                        out.flush();
                    }
                } else {
                    response.setStatus(HttpServletResponse.SC_PARTIAL_CONTENT);
                    long start = range.getStart();
                    long end = range.getEnd();
                    long contentLength = range.getLength();

                    response.setHeader(HttpHeaders.CONTENT_RANGE, "bytes " + start + "-" + end + "/" + totalLength);
                    response.setHeader(HttpHeaders.CONTENT_LENGTH, String.valueOf(contentLength));

                    channel.position(start);

                    try (OutputStream out = response.getOutputStream()) {
                        ByteBuffer buffer = ByteBuffer.allocate(BUFFER_SIZE);
                        long remaining = contentLength;
                        while (remaining > 0) {
                            buffer.clear();
                            int toRead = (int) Math.min(buffer.capacity(), remaining);
                            buffer.limit(toRead);
                            int bytesRead = channel.read(buffer);
                            if (bytesRead == -1) {
                                throw new IOException("Stream read truncated: expected " + contentLength + " bytes but reached EOF with " + remaining + " bytes remaining");
                            }
                            out.write(buffer.array(), buffer.arrayOffset(), bytesRead);
                            remaining -= bytesRead;
                        }
                        out.flush();
                    }
                }
            } catch (Exception e) {
                if (response.isCommitted()) {
                    logger.warn("Stream interrupted after response commit for asset {}: {}", asset.getId(), e.getMessage());
                    throw e;
                } else {
                    if (e instanceof MediaUnavailableException mue) {
                        throw mue;
                    }
                    if (e instanceof IOException ioe) {
                        throw ioe;
                    }
                    throw new MediaUnavailableException("Lỗi khởi tạo luồng phát media: " + e.getMessage());
                }
            }
        } finally {
            mediaStreamService.releaseStreamPermit(asset);
        }
    }

    public int getActiveStreamCount() {
        return mediaStreamService.getActiveStreamCount();
    }

    public int getDriveActiveStreamCount() {
        return mediaStreamService.getDriveActiveStreamCount();
    }
}
