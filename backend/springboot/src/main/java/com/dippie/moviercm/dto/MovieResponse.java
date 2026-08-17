package com.dippie.moviercm.dto;

import com.dippie.moviercm.entity.Movie;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

public class MovieResponse {
    private String id;
    private String title;
    private Integer year;
    private Double rating;
    private String runtime;
    private List<String> genres;
    private String description;
    private String poster;
    private String backdrop;
    private String videoUrl;

    public MovieResponse() {}

    public MovieResponse(String id, String title, Integer year, Double rating, String runtime, List<String> genres, String description, String poster, String backdrop, String videoUrl) {
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
    }

    public static MovieResponse fromEntity(Movie movie) {
        List<String> genreList = Collections.emptyList();
        if (movie.getGenres() != null && !movie.getGenres().trim().isEmpty()) {
            genreList = Arrays.asList(movie.getGenres().split(","));
        }

        return builder()
                .id(movie.getId())
                .title(movie.getTitle())
                .year(movie.getYear())
                .rating(movie.getRating())
                .runtime(movie.getRuntime())
                .description(movie.getDescription())
                .poster(movie.getPoster())
                .backdrop(movie.getBackdrop())
                .videoUrl(movie.getVideoUrl())
                .genres(genreList)
                .build();
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
        private List<String> genres;
        private String description;
        private String poster;
        private String backdrop;
        private String videoUrl;

        public Builder id(String id) { this.id = id; return this; }
        public Builder title(String title) { this.title = title; return this; }
        public Builder year(Integer year) { this.year = year; return this; }
        public Builder rating(Double rating) { this.rating = rating; return this; }
        public Builder runtime(String runtime) { this.runtime = runtime; return this; }
        public Builder genres(List<String> genres) { this.genres = genres; return this; }
        public Builder description(String description) { this.description = description; return this; }
        public Builder poster(String poster) { this.poster = poster; return this; }
        public Builder backdrop(String backdrop) { this.backdrop = backdrop; return this; }
        public Builder videoUrl(String videoUrl) { this.videoUrl = videoUrl; return this; }

        public MovieResponse build() {
            return new MovieResponse(id, title, year, rating, runtime, genres, description, poster, backdrop, videoUrl);
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
    public List<String> getGenres() { return genres; }
    public void setGenres(List<String> genres) { this.genres = genres; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getPoster() { return poster; }
    public void setPoster(String poster) { this.poster = poster; }
    public String getBackdrop() { return backdrop; }
    public void setBackdrop(String backdrop) { this.backdrop = backdrop; }
    public String getVideoUrl() { return videoUrl; }
    public void setVideoUrl(String videoUrl) { this.videoUrl = videoUrl; }
}
