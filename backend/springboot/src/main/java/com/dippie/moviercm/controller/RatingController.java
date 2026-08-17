package com.dippie.moviercm.controller;

import com.dippie.moviercm.dto.ApiResponse;
import com.dippie.moviercm.dto.RatingRequest;
import com.dippie.moviercm.entity.MovieRating;
import com.dippie.moviercm.security.UserDetailsImpl;
import com.dippie.moviercm.service.RatingService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/users/ratings")
public class RatingController {

    private final RatingService ratingService;

    public RatingController(RatingService ratingService) {
        this.ratingService = ratingService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<MovieRating>>> getUserRatings(@AuthenticationPrincipal UserDetailsImpl userDetails) {
        List<MovieRating> ratings = ratingService.getUserRatings(userDetails);
        return ResponseEntity.ok(ApiResponse.success(ratings));
    }

    @PostMapping
    public ResponseEntity<ApiResponse<MovieRating>> rateMovie(
            @AuthenticationPrincipal UserDetailsImpl userDetails,
            @Valid @RequestBody RatingRequest request) {
        MovieRating rating = ratingService.rateMovie(userDetails, request);
        return ResponseEntity.ok(ApiResponse.success("Movie rating saved successfully", rating));
    }
}
