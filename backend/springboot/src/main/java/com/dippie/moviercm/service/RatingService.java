package com.dippie.moviercm.service;

import com.dippie.moviercm.dto.RatingRequest;
import com.dippie.moviercm.entity.MovieRating;
import com.dippie.moviercm.repository.MovieRatingRepository;
import com.dippie.moviercm.security.UserDetailsImpl;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class RatingService {

    private final MovieRatingRepository ratingRepository;

    public RatingService(MovieRatingRepository ratingRepository) {
        this.ratingRepository = ratingRepository;
    }

    @Transactional(readOnly = true)
    public List<MovieRating> getUserRatings(UserDetailsImpl userDetails) {
        return ratingRepository.findByUserId(userDetails.getId());
    }

    @Transactional
    public MovieRating rateMovie(UserDetailsImpl userDetails, RatingRequest request) {
        MovieRating existing = ratingRepository.findByUserIdAndMovieId(userDetails.getId(), request.getMovieId())
                .orElse(null);

        if (existing != null) {
            existing.setRating(request.getRating());
            return ratingRepository.save(existing);
        } else {
            MovieRating newRating = MovieRating.builder()
                    .userId(userDetails.getId())
                    .movieId(request.getMovieId())
                    .rating(request.getRating())
                    .build();
            return ratingRepository.save(newRating);
        }
    }
}
