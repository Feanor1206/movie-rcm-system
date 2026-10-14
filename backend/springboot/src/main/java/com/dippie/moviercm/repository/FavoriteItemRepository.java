package com.dippie.moviercm.repository;

import com.dippie.moviercm.entity.FavoriteItem;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface FavoriteItemRepository extends JpaRepository<FavoriteItem, Long> {
    List<FavoriteItem> findByUserId(Long userId);
    List<FavoriteItem> findByUserIdOrderByAddedAtDesc(Long userId);
    Optional<FavoriteItem> findByUserIdAndMovieId(Long userId, String movieId);
    Boolean existsByUserIdAndMovieId(Long userId, String movieId);
    void deleteByUserIdAndMovieId(Long userId, String movieId);
}
