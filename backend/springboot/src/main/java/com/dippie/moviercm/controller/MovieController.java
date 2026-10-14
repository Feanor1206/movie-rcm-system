package com.dippie.moviercm.controller;

import com.dippie.moviercm.dto.ApiResponse;
import com.dippie.moviercm.dto.MovieResponse;
import com.dippie.moviercm.dto.PageResponse;
import com.dippie.moviercm.service.MovieService;
import org.springframework.http.HttpStatus;
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
        List<MovieResponse> movies = movieService.getAllMovies(search, genre);
        return ResponseEntity.ok(ApiResponse.success(movies));
    }

    @GetMapping("/browse")
    public ResponseEntity<ApiResponse<PageResponse<MovieResponse>>> browseMovies(
            @RequestParam(required = false) String search,
            @RequestParam(required = false) String query,
            @RequestParam(required = false) String genre,
            @RequestParam(required = false) String genres,
            @RequestParam(required = false, defaultValue = "false") Boolean animationOnly,
            @RequestParam(required = false) Integer yearMin,
            @RequestParam(required = false) Integer yearMax,
            @RequestParam(required = false, defaultValue = "rating") String sort,
            @RequestParam(required = false, defaultValue = "desc") String direction,
            @RequestParam(required = false, defaultValue = "0") int page,
            @RequestParam(required = false, defaultValue = "12") int size) {
        String effectiveQuery = (query != null && !query.trim().isEmpty()) ? query : search;
        PageResponse<MovieResponse> pageResponse = movieService.browseMovies(
                effectiveQuery,
                genre,
                genres,
                animationOnly,
                yearMin,
                yearMax,
                sort,
                direction,
                page,
                size
        );
        return ResponseEntity.ok(ApiResponse.success(pageResponse));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<MovieResponse>> getMovieById(@PathVariable String id) {
        try {
            MovieResponse movie = movieService.getMovieById(id);
            return ResponseEntity.ok(ApiResponse.success(movie));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(ApiResponse.error("Movie not found with id: " + id));
        }
    }
}
