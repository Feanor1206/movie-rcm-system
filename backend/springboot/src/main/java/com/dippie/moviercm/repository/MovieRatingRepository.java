package com.dippie.moviercm.repository;

import com.dippie.moviercm.entity.MovieRating;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface MovieRatingRepository extends JpaRepository<MovieRating, Long> {
    List<MovieRating> findByUserId(Long userId);
    List<MovieRating> findByUserIdOrderByUpdatedAtDesc(Long userId);
    Optional<MovieRating> findByUserIdAndMovieId(Long userId, String movieId);
    Boolean existsByUserIdAndMovieId(Long userId, String movieId);
}
