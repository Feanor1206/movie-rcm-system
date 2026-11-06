package com.dippie.moviercm.controller;

import com.dippie.moviercm.dto.MediaDescriptorResponse;
import com.dippie.moviercm.service.MediaStreamService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/movies")
public class MediaDescriptorController {

    private final MediaStreamService mediaStreamService;

    public MediaDescriptorController(MediaStreamService mediaStreamService) {
        this.mediaStreamService = mediaStreamService;
    }

    @GetMapping("/{movieId}/media-descriptor")
    public ResponseEntity<MediaDescriptorResponse> getMediaDescriptor(@PathVariable String movieId) {
        MediaDescriptorResponse descriptor = mediaStreamService.getMediaDescriptor(movieId);
        return ResponseEntity.ok(descriptor);
    }
}
