package com.dippie.moviercm.service;

import com.dippie.moviercm.dto.WatchlistRequest;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.entity.WatchlistItem;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.repository.WatchlistItemRepository;
import com.dippie.moviercm.security.UserDetailsImpl;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

@Service
public class WatchlistService {

    private final WatchlistItemRepository watchlistRepository;
    private final MovieRepository movieRepository;
    private final LibraryPersistenceHelper persistenceHelper;

    public WatchlistService(WatchlistItemRepository watchlistRepository,
                            MovieRepository movieRepository,
                            LibraryPersistenceHelper persistenceHelper) {
        this.watchlistRepository = watchlistRepository;
        this.movieRepository = movieRepository;
        this.persistenceHelper = persistenceHelper;
    }

    @Transactional(readOnly = true)
    public List<WatchlistItem> getUserWatchlist(UserDetailsImpl userDetails) {
        return watchlistRepository.findByUserIdOrderByAddedAtDesc(userDetails.getId());
    }

    public WatchlistItem addToWatchlist(UserDetailsImpl userDetails, WatchlistRequest request) {
        // 1. Strict catalog validation (R5)
        Movie movie = movieRepository.findById(request.getMovieId())
                .orElseThrow(() -> new IllegalArgumentException("Phim không tồn tại trong danh mục: " + request.getMovieId()));

        // 2. Check if already present for user
        Optional<WatchlistItem> existing = watchlistRepository.findByUserIdAndMovieId(userDetails.getId(), request.getMovieId());
        if (existing.isPresent()) {
            return existing.get();
        }

        // 3. Build item with canonical metadata from catalog (R5)
        WatchlistItem item = WatchlistItem.builder()
                .userId(userDetails.getId())
                .movieId(movie.getId())
                .movieTitle(movie.getTitle())
                .posterUrl(movie.getPoster())
                .build();

        // 4. Save with concurrent idempotency race recovery (R6)
        try {
            return persistenceHelper.saveWatchlistItem(item);
        } catch (DataIntegrityViolationException e) {
            return watchlistRepository.findByUserIdAndMovieId(userDetails.getId(), request.getMovieId())
                    .orElseThrow(() -> new IllegalStateException("Không thể lưu mục vào watchlist do xung đột cơ sở dữ liệu: " + request.getMovieId()));
        }
    }

    @Transactional
    public void removeFromWatchlist(UserDetailsImpl userDetails, String movieId) {
        // Allows orphan deletion without requiring catalog entry
        watchlistRepository.deleteByUserIdAndMovieId(userDetails.getId(), movieId);
    }
}
