package com.dippie.moviercm.dto;

import jakarta.validation.constraints.NotBlank;

public class WatchlistRequest {

    @NotBlank(message = "Movie ID is required")
    private String movieId;

    private String movieTitle;
    private String posterUrl;

    public WatchlistRequest() {}

    public WatchlistRequest(String movieId, String movieTitle, String posterUrl) {
        this.movieId = movieId;
        this.movieTitle = movieTitle;
        this.posterUrl = posterUrl;
    }

    public String getMovieId() { return movieId; }
    public void setMovieId(String movieId) { this.movieId = movieId; }
    public String getMovieTitle() { return movieTitle; }
    public void setMovieTitle(String movieTitle) { this.movieTitle = movieTitle; }
    public String getPosterUrl() { return posterUrl; }
    public void setPosterUrl(String posterUrl) { this.posterUrl = posterUrl; }
}
