package com.dippie.moviercm.controller;

import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.service.MediaStreamService;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.io.Resource;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

@RestController
@RequestMapping("/api/media")
public class MediaStreamController {

    private static final int BUFFER_SIZE = 64 * 1024; // 64 KiB bounded buffer

    private final MediaStreamService mediaStreamService;

    public MediaStreamController(MediaStreamService mediaStreamService) {
        this.mediaStreamService = mediaStreamService;
    }

    @RequestMapping(value = "/stream/{assetId}", method = RequestMethod.HEAD)
    public ResponseEntity<Void> getStreamHeaders(@PathVariable String assetId) {
        MediaAsset asset = mediaStreamService.getMediaAsset(assetId);
        long length = mediaStreamService.getResourceLength(asset);

        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(asset.getMimeType()))
                .contentLength(length)
                .header(HttpHeaders.ACCEPT_RANGES, "bytes")
                .eTag(asset.getId() + "-" + asset.getVersion())
                .cacheControl(CacheControl.maxAge(3600, java.util.concurrent.TimeUnit.SECONDS).cachePublic())
                .build();
    }

    @GetMapping("/stream/{assetId}")
    public void streamMedia(
            @PathVariable String assetId,
            @RequestHeader(value = HttpHeaders.RANGE, required = false) String rangeHeader,
            HttpServletResponse response) throws IOException {

        MediaAsset asset = mediaStreamService.getMediaAsset(assetId);
        Resource resource = mediaStreamService.getMediaResource(asset);
        long totalLength = mediaStreamService.getResourceLength(asset);

        MediaStreamService.RangeSpec range = mediaStreamService.parseRange(rangeHeader, totalLength);

        response.setHeader(HttpHeaders.ACCEPT_RANGES, "bytes");
        response.setHeader(HttpHeaders.ETAG, "\"" + asset.getId() + "-" + asset.getVersion() + "\"");
        response.setHeader(HttpHeaders.CACHE_CONTROL, "public, max-age=3600");
        response.setContentType(asset.getMimeType());

        if (!range.isRanged()) {
            response.setStatus(HttpServletResponse.SC_OK);
            response.setHeader(HttpHeaders.CONTENT_LENGTH, String.valueOf(totalLength));
            try (InputStream in = resource.getInputStream();
                 OutputStream out = response.getOutputStream()) {
                byte[] buffer = new byte[BUFFER_SIZE];
                int bytesRead;
                while ((bytesRead = in.read(buffer)) != -1) {
                    out.write(buffer, 0, bytesRead);
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

            try (InputStream in = resource.getInputStream();
                 OutputStream out = response.getOutputStream()) {
                long skipped = in.skip(start);
                while (skipped < start) {
                    long s = in.skip(start - skipped);
                    if (s <= 0) break;
                    skipped += s;
                }

                byte[] buffer = new byte[BUFFER_SIZE];
                long remaining = contentLength;
                while (remaining > 0) {
                    int toRead = (int) Math.min(buffer.length, remaining);
                    int bytesRead = in.read(buffer, 0, toRead);
                    if (bytesRead == -1) break;
                    out.write(buffer, 0, bytesRead);
                    remaining -= bytesRead;
                }
                out.flush();
            }
        }
    }
}

