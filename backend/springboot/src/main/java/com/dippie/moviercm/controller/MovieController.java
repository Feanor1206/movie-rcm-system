package com.dippie.moviercm.controller;

import com.dippie.moviercm.dto.ApiResponse;
import com.dippie.moviercm.dto.MovieResponse;
import com.dippie.moviercm.service.MovieService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/movies")
public class MovieController {

    private final MovieService movieService;

    public MovieController(MovieService movieService) {
        this.movieService = movieService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<MovieResponse>>> getAllMovies(
            @RequestParam(required = false) String search,
            @RequestParam(required = false) String genre) {
        List<MovieResponse> movies;
        if (search != null && !search.trim().isEmpty()) {
            movies = movieService.searchMovies(search);
        } else if (genre != null && !genre.trim().isEmpty()) {
            movies = movieService.filterByGenre(genre);
        } else {
            movies = movieService.getAllMovies();
        }
        return ResponseEntity.ok(ApiResponse.success(movies));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<MovieResponse>> getMovieById(@PathVariable String id) {
        MovieResponse movie = movieService.getMovieById(id);
        return ResponseEntity.ok(ApiResponse.success(movie));
    }
}
