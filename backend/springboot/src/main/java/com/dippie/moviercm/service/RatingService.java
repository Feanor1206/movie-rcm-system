package com.dippie.moviercm.service;

import com.dippie.moviercm.dto.RatingRequest;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.entity.MovieRating;
import com.dippie.moviercm.repository.MovieRatingRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.security.UserDetailsImpl;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

@Service
public class RatingService {

    private final MovieRatingRepository ratingRepository;
    private final MovieRepository movieRepository;
    private final LibraryPersistenceHelper persistenceHelper;

    public RatingService(MovieRatingRepository ratingRepository,
                         MovieRepository movieRepository,
                         LibraryPersistenceHelper persistenceHelper) {
        this.ratingRepository = ratingRepository;
        this.movieRepository = movieRepository;
        this.persistenceHelper = persistenceHelper;
    }

    @Transactional(readOnly = true)
    public List<MovieRating> getUserRatings(UserDetailsImpl userDetails) {
        return ratingRepository.findByUserIdOrderByUpdatedAtDesc(userDetails.getId());
    }

    public MovieRating rateMovie(UserDetailsImpl userDetails, RatingRequest request) {
        // 1. Strict catalog validation (R5)
        Movie movie = movieRepository.findById(request.getMovieId())
                .orElseThrow(() -> new IllegalArgumentException("Phim không tồn tại trong danh mục: " + request.getMovieId()));

        // 2. Check if already rated by user -> update
        Optional<MovieRating> existing = ratingRepository.findByUserIdAndMovieId(userDetails.getId(), request.getMovieId());
        if (existing.isPresent()) {
            MovieRating r = existing.get();
            r.setRating(request.getRating());
            return ratingRepository.save(r);
        }

        // 3. New rating: save with concurrent race recovery (R6)
        MovieRating newRating = MovieRating.builder()
                .userId(userDetails.getId())
                .movieId(movie.getId())
                .rating(request.getRating())
                .build();

        try {
            return persistenceHelper.saveMovieRating(newRating);
        } catch (DataIntegrityViolationException e) {
            // Concurrent race: another thread created the rating record simultaneously
            // Policy: update the existing record with this request's rating
            MovieRating r = ratingRepository.findByUserIdAndMovieId(userDetails.getId(), request.getMovieId())
                    .orElseThrow(() -> new IllegalStateException("Không thể lưu điểm đánh giá do xung đột cơ sở dữ liệu: " + request.getMovieId()));
            r.setRating(request.getRating());
            return ratingRepository.save(r);
        }
    }

    @Transactional
    public void deleteRating(UserDetailsImpl userDetails, String movieId) {
        // Allows orphan deletion without requiring catalog entry
        ratingRepository.deleteByUserIdAndMovieId(userDetails.getId(), movieId);
    }
}
