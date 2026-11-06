package com.dippie.moviercm.service;

import com.dippie.moviercm.dto.FavoriteRequest;
import com.dippie.moviercm.entity.FavoriteItem;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.repository.FavoriteItemRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.security.UserDetailsImpl;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

@Service
public class FavoriteService {

    private final FavoriteItemRepository favoriteRepository;
    private final MovieRepository movieRepository;
    private final LibraryPersistenceHelper persistenceHelper;

    public FavoriteService(FavoriteItemRepository favoriteRepository,
                           MovieRepository movieRepository,
                           LibraryPersistenceHelper persistenceHelper) {
        this.favoriteRepository = favoriteRepository;
        this.movieRepository = movieRepository;
        this.persistenceHelper = persistenceHelper;
    }

    @Transactional(readOnly = true)
    public List<FavoriteItem> getUserFavorites(UserDetailsImpl userDetails) {
        return favoriteRepository.findByUserIdOrderByAddedAtDesc(userDetails.getId());
    }

    public FavoriteItem addToFavorites(UserDetailsImpl userDetails, FavoriteRequest request) {
        // 1. Strict catalog validation (R5)
        Movie movie = movieRepository.findById(request.getMovieId())
                .orElseThrow(() -> new IllegalArgumentException("Phim không tồn tại trong danh mục: " + request.getMovieId()));

        // 2. Check if already present for user
        Optional<FavoriteItem> existing = favoriteRepository.findByUserIdAndMovieId(userDetails.getId(), request.getMovieId());
        if (existing.isPresent()) {
            return existing.get();
        }

        // 3. Build item with canonical metadata from catalog (R5)
        FavoriteItem item = FavoriteItem.builder()
                .userId(userDetails.getId())
                .movieId(movie.getId())
                .movieTitle(movie.getTitle())
                .posterUrl(movie.getPoster())
                .build();

        // 4. Save with concurrent idempotency race recovery (R6)
        try {
            return persistenceHelper.saveFavoriteItem(item);
        } catch (DataIntegrityViolationException e) {
            return favoriteRepository.findByUserIdAndMovieId(userDetails.getId(), request.getMovieId())
                    .orElseThrow(() -> new IllegalStateException("Không thể lưu mục yêu thích do xung đột cơ sở dữ liệu: " + request.getMovieId()));
        }
    }

    @Transactional
    public void removeFromFavorites(UserDetailsImpl userDetails, String movieId) {
        // Allows orphan deletion without requiring catalog entry
        favoriteRepository.deleteByUserIdAndMovieId(userDetails.getId(), movieId);
    }
}
