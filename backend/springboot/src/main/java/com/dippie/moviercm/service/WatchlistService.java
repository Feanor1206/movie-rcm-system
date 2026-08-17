package com.dippie.moviercm.service;

import com.dippie.moviercm.dto.WatchlistRequest;
import com.dippie.moviercm.entity.WatchlistItem;
import com.dippie.moviercm.repository.WatchlistItemRepository;
import com.dippie.moviercm.security.UserDetailsImpl;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class WatchlistService {

    private final WatchlistItemRepository watchlistRepository;

    public WatchlistService(WatchlistItemRepository watchlistRepository) {
        this.watchlistRepository = watchlistRepository;
    }

    @Transactional(readOnly = true)
    public List<WatchlistItem> getUserWatchlist(UserDetailsImpl userDetails) {
        return watchlistRepository.findByUserId(userDetails.getId());
    }

    @Transactional
    public WatchlistItem addToWatchlist(UserDetailsImpl userDetails, WatchlistRequest request) {
        if (watchlistRepository.existsByUserIdAndMovieId(userDetails.getId(), request.getMovieId())) {
            throw new IllegalArgumentException("Movie is already in your watchlist!");
        }

        WatchlistItem item = WatchlistItem.builder()
                .userId(userDetails.getId())
                .movieId(request.getMovieId())
                .movieTitle(request.getMovieTitle())
                .posterUrl(request.getPosterUrl())
                .build();

        return watchlistRepository.save(item);
    }

    @Transactional
    public void removeFromWatchlist(UserDetailsImpl userDetails, String movieId) {
        watchlistRepository.deleteByUserIdAndMovieId(userDetails.getId(), movieId);
    }
}
