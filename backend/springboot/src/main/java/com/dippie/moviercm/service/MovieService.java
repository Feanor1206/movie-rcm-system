package com.dippie.moviercm.service;

import com.dippie.moviercm.dto.MovieResponse;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.repository.MovieRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class MovieService {

    private final MovieRepository movieRepository;

    public MovieService(MovieRepository movieRepository) {
        this.movieRepository = movieRepository;
    }

    @Transactional(readOnly = true)
    public List<MovieResponse> getAllMovies() {
        return movieRepository.findAll().stream()
                .map(MovieResponse::fromEntity)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public MovieResponse getMovieById(String id) {
        Movie movie = movieRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Movie not found with id: " + id));
        return MovieResponse.fromEntity(movie);
    }

    @Transactional(readOnly = true)
    public List<MovieResponse> searchMovies(String query) {
        if (query == null || query.trim().isEmpty()) {
            return getAllMovies();
        }
        return movieRepository.findByTitleContainingIgnoreCase(query.trim()).stream()
                .map(MovieResponse::fromEntity)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public List<MovieResponse> filterByGenre(String genre) {
        if (genre == null || genre.trim().isEmpty()) {
            return getAllMovies();
        }
        return movieRepository.findByGenresContainingIgnoreCase(genre.trim()).stream()
                .map(MovieResponse::fromEntity)
                .collect(Collectors.toList());
    }
}
