package com.dippie.moviercm.dto;

public class MediaDescriptorResponse {

    private String movieId;
    private boolean hasFeature;
    private boolean hasTrailer;
    private MediaAssetDto feature;
    private MediaAssetDto trailer;

    public MediaDescriptorResponse() {}

    public MediaDescriptorResponse(String movieId, boolean hasFeature, boolean hasTrailer,
                                   MediaAssetDto feature, MediaAssetDto trailer) {
        this.movieId = movieId;
        this.hasFeature = hasFeature;
        this.hasTrailer = hasTrailer;
        this.feature = feature;
        this.trailer = trailer;
    }

    public String getMovieId() {
        return movieId;
    }

    public void setMovieId(String movieId) {
        this.movieId = movieId;
    }

    public boolean isHasFeature() {
        return hasFeature;
    }

    public void setHasFeature(boolean hasFeature) {
        this.hasFeature = hasFeature;
    }

    public boolean isHasTrailer() {
        return hasTrailer;
    }

    public void setHasTrailer(boolean hasTrailer) {
        this.hasTrailer = hasTrailer;
    }

    public MediaAssetDto getFeature() {
        return feature;
    }

    public void setFeature(MediaAssetDto feature) {
        this.feature = feature;
    }

    public MediaAssetDto getTrailer() {
        return trailer;
    }

    public void setTrailer(MediaAssetDto trailer) {
        this.trailer = trailer;
    }
}
