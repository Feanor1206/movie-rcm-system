package com.dippie.moviercm.repository;

import com.dippie.moviercm.entity.WatchlistItem;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface WatchlistItemRepository extends JpaRepository<WatchlistItem, Long> {
    List<WatchlistItem> findByUserId(Long userId);
    List<WatchlistItem> findByUserIdOrderByAddedAtDesc(Long userId);
    Optional<WatchlistItem> findByUserIdAndMovieId(Long userId, String movieId);
    Boolean existsByUserIdAndMovieId(Long userId, String movieId);
    void deleteByUserIdAndMovieId(Long userId, String movieId);
}
