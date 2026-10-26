package com.dippie.moviercm.dto;

import java.time.LocalDateTime;

public class WatchProgressResponse {

    private final String episodeId;
    private final String seriesId;
    private final String seriesTitle;
    private final String seasonId;
    private final Integer seasonNumber;
    private final String seasonTitle;
    private final Integer episodeNumber;
    private final String episodeTitle;
    private final String assetId;
    private final long positionMs;
    private final Long durationMs;
    private final boolean completed;
    private final long version;
    private final LocalDateTime updatedAt;

    public WatchProgressResponse(String episodeId, String seriesId, String seriesTitle,
                                 String seasonId, Integer seasonNumber, String seasonTitle,
                                 Integer episodeNumber, String episodeTitle, String assetId,
                                 long positionMs, Long durationMs, boolean completed,
                                 long version, LocalDateTime updatedAt) {
        this.episodeId = episodeId;
        this.seriesId = seriesId;
        this.seriesTitle = seriesTitle;
        this.seasonId = seasonId;
        this.seasonNumber = seasonNumber;
        this.seasonTitle = seasonTitle;
        this.episodeNumber = episodeNumber;
        this.episodeTitle = episodeTitle;
        this.assetId = assetId;
        this.positionMs = positionMs;
        this.durationMs = durationMs;
        this.completed = completed;
        this.version = version;
        this.updatedAt = updatedAt;
    }

    public String getEpisodeId() { return episodeId; }
    public String getSeriesId() { return seriesId; }
    public String getSeriesTitle() { return seriesTitle; }
    public String getSeasonId() { return seasonId; }
    public Integer getSeasonNumber() { return seasonNumber; }
    public String getSeasonTitle() { return seasonTitle; }
    public Integer getEpisodeNumber() { return episodeNumber; }
    public String getEpisodeTitle() { return episodeTitle; }
    public String getAssetId() { return assetId; }
    public long getPositionMs() { return positionMs; }
    public Long getDurationMs() { return durationMs; }
    public boolean isCompleted() { return completed; }
    public long getVersion() { return version; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
}
