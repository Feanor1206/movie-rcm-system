package com.dippie.moviercm.service;

import com.dippie.moviercm.entity.FavoriteItem;
import com.dippie.moviercm.entity.MovieRating;
import com.dippie.moviercm.entity.WatchlistItem;
import com.dippie.moviercm.repository.FavoriteItemRepository;
import com.dippie.moviercm.repository.MovieRatingRepository;
import com.dippie.moviercm.repository.WatchlistItemRepository;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/**
 * Helper bean isolating single-item library persistence in dedicated REQUIRES_NEW transactions.
 * This guarantees that concurrent insert collisions (triggering DataIntegrityViolationException
 * due to unique constraints) do not mark the outer calling transaction as rollback-only.
 */
@Component
public class LibraryPersistenceHelper {

    private final WatchlistItemRepository watchlistRepository;
    private final FavoriteItemRepository favoriteRepository;
    private final MovieRatingRepository ratingRepository;

    public LibraryPersistenceHelper(WatchlistItemRepository watchlistRepository,
                                    FavoriteItemRepository favoriteRepository,
                                    MovieRatingRepository ratingRepository) {
        this.watchlistRepository = watchlistRepository;
        this.favoriteRepository = favoriteRepository;
        this.ratingRepository = ratingRepository;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public WatchlistItem saveWatchlistItem(WatchlistItem item) {
        return watchlistRepository.saveAndFlush(item);
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public FavoriteItem saveFavoriteItem(FavoriteItem item) {
        return favoriteRepository.saveAndFlush(item);
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public MovieRating saveMovieRating(MovieRating item) {
        return ratingRepository.saveAndFlush(item);
    }
}
