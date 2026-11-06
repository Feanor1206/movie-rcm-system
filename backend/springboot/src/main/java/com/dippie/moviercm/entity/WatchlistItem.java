package com.dippie.moviercm.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;

@Entity
@Table(name = "watchlist_items", uniqueConstraints = {
    @UniqueConstraint(columnNames = {"user_id", "movie_id"})
})
public class WatchlistItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "movie_id", nullable = false, length = 100)
    private String movieId;

    @Column(nullable = false, length = 255)
    private String movieTitle;

    @Column(length = 500)
    private String posterUrl;

    @CreationTimestamp
    @Column(updatable = false)
    private LocalDateTime addedAt;

    public WatchlistItem() {}

    public WatchlistItem(Long id, Long userId, String movieId, String movieTitle, String posterUrl, LocalDateTime addedAt) {
        this.id = id;
        this.userId = userId;
        this.movieId = movieId;
        this.movieTitle = movieTitle;
        this.posterUrl = posterUrl;
        this.addedAt = addedAt;
    }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private Long id;
        private Long userId;
        private String movieId;
        private String movieTitle;
        private String posterUrl;
        private LocalDateTime addedAt;

        public Builder id(Long id) { this.id = id; return this; }
        public Builder userId(Long userId) { this.userId = userId; return this; }
        public Builder movieId(String movieId) { this.movieId = movieId; return this; }
        public Builder movieTitle(String movieTitle) { this.movieTitle = movieTitle; return this; }
        public Builder posterUrl(String posterUrl) { this.posterUrl = posterUrl; return this; }
        public Builder addedAt(LocalDateTime addedAt) { this.addedAt = addedAt; return this; }

        public WatchlistItem build() {
            return new WatchlistItem(id, userId, movieId, movieTitle, posterUrl, addedAt);
        }
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }
    public String getMovieId() { return movieId; }
    public void setMovieId(String movieId) { this.movieId = movieId; }
    public String getMovieTitle() { return movieTitle; }
    public void setMovieTitle(String movieTitle) { this.movieTitle = movieTitle; }
    public String getPosterUrl() { return posterUrl; }
    public void setPosterUrl(String posterUrl) { this.posterUrl = posterUrl; }
    public LocalDateTime getAddedAt() { return addedAt; }
    public void setAddedAt(LocalDateTime addedAt) { this.addedAt = addedAt; }
}
