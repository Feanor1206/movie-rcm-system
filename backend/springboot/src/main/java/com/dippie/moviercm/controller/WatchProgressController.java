package com.dippie.moviercm.controller;

import com.dippie.moviercm.dto.ApiResponse;
import com.dippie.moviercm.dto.WatchProgressRequest;
import com.dippie.moviercm.dto.WatchProgressResponse;
import com.dippie.moviercm.security.UserDetailsImpl;
import com.dippie.moviercm.service.WatchProgressService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/users/watch-progress")
public class WatchProgressController {

    private final WatchProgressService watchProgressService;

    public WatchProgressController(WatchProgressService watchProgressService) {
        this.watchProgressService = watchProgressService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<WatchProgressResponse>>> getRecent(
            @AuthenticationPrincipal UserDetailsImpl user) {
        return ResponseEntity.ok(ApiResponse.success(watchProgressService.getRecent(user)));
    }

    @GetMapping("/{episodeId}")
    public ResponseEntity<ApiResponse<WatchProgressResponse>> getForEpisode(
            @AuthenticationPrincipal UserDetailsImpl user,
            @PathVariable String episodeId) {
        return ResponseEntity.ok(ApiResponse.success(watchProgressService.getForEpisode(user, episodeId)));
    }

    @PutMapping("/{episodeId}")
    public ResponseEntity<ApiResponse<WatchProgressResponse>> save(
            @AuthenticationPrincipal UserDetailsImpl user,
            @PathVariable String episodeId,
            @Valid @RequestBody WatchProgressRequest request) {
        return ResponseEntity.ok(ApiResponse.success("Watch progress saved", watchProgressService.save(user, episodeId, request)));
    }

    @DeleteMapping("/{episodeId}")
    public ResponseEntity<ApiResponse<Void>> delete(
            @AuthenticationPrincipal UserDetailsImpl user,
            @PathVariable String episodeId) {
        watchProgressService.delete(user, episodeId);
        return ResponseEntity.ok(ApiResponse.success("Watch progress deleted", null));
    }
}
