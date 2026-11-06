package com.dippie.moviercm.dto.catalog;

public class CatalogSearchResult {
    private String id;
    private String type; // "series", "episode", "segment", "scene"
    private String title;
    private String parentTitle;
    private String seriesId;
    private String episodeId;
    private String mediaAssetId;
    private Long startMs;
    private Long endMs;
    private String snippet;

    public CatalogSearchResult() {}

    public CatalogSearchResult(String id, String type, String title, String parentTitle,
                               String seriesId, String episodeId, String mediaAssetId,
                               Long startMs, Long endMs, String snippet) {
        this.id = id;
        this.type = type;
        this.title = title;
        this.parentTitle = parentTitle;
        this.seriesId = seriesId;
        this.episodeId = episodeId;
        this.mediaAssetId = mediaAssetId;
        this.startMs = startMs;
        this.endMs = endMs;
        this.snippet = snippet;
    }

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getType() { return type; }
    public void setType(String type) { this.type = type; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getParentTitle() { return parentTitle; }
    public void setParentTitle(String parentTitle) { this.parentTitle = parentTitle; }

    public String getSeriesId() { return seriesId; }
    public void setSeriesId(String seriesId) { this.seriesId = seriesId; }

    public String getEpisodeId() { return episodeId; }
    public void setEpisodeId(String episodeId) { this.episodeId = episodeId; }

    public String getMediaAssetId() { return mediaAssetId; }
    public void setMediaAssetId(String mediaAssetId) { this.mediaAssetId = mediaAssetId; }

    public Long getStartMs() { return startMs; }
    public void setStartMs(Long startMs) { this.startMs = startMs; }

    public Long getEndMs() { return endMs; }
    public void setEndMs(Long endMs) { this.endMs = endMs; }

    public String getSnippet() { return snippet; }
    public void setSnippet(String snippet) { this.snippet = snippet; }
}
