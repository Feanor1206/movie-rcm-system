package com.dippie.moviercm.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;

@Entity
@Table(name = "movies")
public class Movie {

    @Id
    @Column(length = 100)
    private String id;

    @Column(nullable = false, length = 255)
    private String title;

    @Column(name = "release_year", nullable = false)
    private Integer year;

    @Column(nullable = false)
    private Double rating;

    @Column(length = 20)
    private String runtime;

    @Column(columnDefinition = "TEXT")
    private String genres;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Column(length = 500)
    private String poster;

    @Column(length = 500)
    private String backdrop;

    @Column(length = 500)
    private String videoUrl;

    @CreationTimestamp
    @Column(updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    private LocalDateTime updatedAt;

    public Movie() {}

    public Movie(String id, String title, Integer year, Double rating, String runtime, String genres, String description, String poster, String backdrop, String videoUrl, LocalDateTime createdAt, LocalDateTime updatedAt) {
        this.id = id;
        this.title = title;
        this.year = year;
        this.rating = rating;
        this.runtime = runtime;
        this.genres = genres;
        this.description = description;
        this.poster = poster;
        this.backdrop = backdrop;
        this.videoUrl = videoUrl;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String id;
        private String title;
        private Integer year;
        private Double rating;
        private String runtime;
        private String genres;
        private String description;
        private String poster;
        private String backdrop;
        private String videoUrl;
        private LocalDateTime createdAt;
        private LocalDateTime updatedAt;

        public Builder id(String id) { this.id = id; return this; }
        public Builder title(String title) { this.title = title; return this; }
        public Builder year(Integer year) { this.year = year; return this; }
        public Builder rating(Double rating) { this.rating = rating; return this; }
        public Builder runtime(String runtime) { this.runtime = runtime; return this; }
        public Builder genres(String genres) { this.genres = genres; return this; }
        public Builder description(String description) { this.description = description; return this; }
        public Builder poster(String poster) { this.poster = poster; return this; }
        public Builder backdrop(String backdrop) { this.backdrop = backdrop; return this; }
        public Builder videoUrl(String videoUrl) { this.videoUrl = videoUrl; return this; }
        public Builder createdAt(LocalDateTime createdAt) { this.createdAt = createdAt; return this; }
        public Builder updatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; return this; }

        public Movie build() {
            return new Movie(id, title, year, rating, runtime, genres, description, poster, backdrop, videoUrl, createdAt, updatedAt);
        }
    }

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public Integer getYear() { return year; }
    public void setYear(Integer year) { this.year = year; }
    public Double getRating() { return rating; }
    public void setRating(Double rating) { this.rating = rating; }
    public String getRuntime() { return runtime; }
    public void setRuntime(String runtime) { this.runtime = runtime; }
    public String getGenres() { return genres; }
    public void setGenres(String genres) { this.genres = genres; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getPoster() { return poster; }
    public void setPoster(String poster) { this.poster = poster; }
    public String getBackdrop() { return backdrop; }
    public void setBackdrop(String backdrop) { this.backdrop = backdrop; }
    public String getVideoUrl() { return videoUrl; }
    public void setVideoUrl(String videoUrl) { this.videoUrl = videoUrl; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
