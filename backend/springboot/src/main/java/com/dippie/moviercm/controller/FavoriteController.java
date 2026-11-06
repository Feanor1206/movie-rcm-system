package com.dippie.moviercm.controller;

import com.dippie.moviercm.dto.ApiResponse;
import com.dippie.moviercm.dto.FavoriteRequest;
import com.dippie.moviercm.entity.FavoriteItem;
import com.dippie.moviercm.security.UserDetailsImpl;
import com.dippie.moviercm.service.FavoriteService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/users/favorites")
public class FavoriteController {

    private final FavoriteService favoriteService;

    public FavoriteController(FavoriteService favoriteService) {
        this.favoriteService = favoriteService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<FavoriteItem>>> getUserFavorites(@AuthenticationPrincipal UserDetailsImpl userDetails) {
        List<FavoriteItem> favorites = favoriteService.getUserFavorites(userDetails);
        return ResponseEntity.ok(ApiResponse.success(favorites));
    }

    @PostMapping
    public ResponseEntity<ApiResponse<FavoriteItem>> addToFavorites(
            @AuthenticationPrincipal UserDetailsImpl userDetails,
            @Valid @RequestBody FavoriteRequest request) {
        FavoriteItem item = favoriteService.addToFavorites(userDetails, request);
        return ResponseEntity.ok(ApiResponse.success("Movie added to favorites", item));
    }

    @DeleteMapping("/{movieId}")
    public ResponseEntity<ApiResponse<Void>> removeFromFavorites(
            @AuthenticationPrincipal UserDetailsImpl userDetails,
            @PathVariable String movieId) {
        favoriteService.removeFromFavorites(userDetails, movieId);
        return ResponseEntity.ok(ApiResponse.success("Movie removed from favorites", null));
    }
}
