package com.dippie.moviercm.controller;

import com.dippie.moviercm.dto.ApiResponse;
import com.dippie.moviercm.dto.WatchlistRequest;
import com.dippie.moviercm.entity.WatchlistItem;
import com.dippie.moviercm.security.UserDetailsImpl;
import com.dippie.moviercm.service.WatchlistService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/users/watchlist")
public class WatchlistController {

    private final WatchlistService watchlistService;

    public WatchlistController(WatchlistService watchlistService) {
        this.watchlistService = watchlistService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<WatchlistItem>>> getUserWatchlist(@AuthenticationPrincipal UserDetailsImpl userDetails) {
        List<WatchlistItem> watchlist = watchlistService.getUserWatchlist(userDetails);
        return ResponseEntity.ok(ApiResponse.success(watchlist));
    }

    @PostMapping
    public ResponseEntity<ApiResponse<WatchlistItem>> addToWatchlist(
            @AuthenticationPrincipal UserDetailsImpl userDetails,
            @Valid @RequestBody WatchlistRequest request) {
        WatchlistItem item = watchlistService.addToWatchlist(userDetails, request);
        return ResponseEntity.ok(ApiResponse.success("Movie added to watchlist", item));
    }

    @DeleteMapping("/{movieId}")
    public ResponseEntity<ApiResponse<Void>> removeFromWatchlist(
            @AuthenticationPrincipal UserDetailsImpl userDetails,
            @PathVariable String movieId) {
        watchlistService.removeFromWatchlist(userDetails, movieId);
        return ResponseEntity.ok(ApiResponse.success("Movie removed from watchlist", null));
    }
}
