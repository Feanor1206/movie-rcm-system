package com.dippie.moviercm.dto.catalog;

import com.dippie.moviercm.entity.catalog.CatalogEpisode;
import com.dippie.moviercm.entity.catalog.CatalogMediaAsset;
import com.dippie.moviercm.entity.catalog.CatalogScene;
import com.dippie.moviercm.entity.catalog.CatalogSegment;

import java.util.List;

public class CatalogEpisodeResponse {
    private CatalogEpisode episode;
    private List<CatalogSegment> segments;
    private List<CatalogMediaAsset> mediaAssets;
    private List<CatalogScene> scenes;

    public CatalogEpisodeResponse() {}

    public CatalogEpisodeResponse(CatalogEpisode episode, List<CatalogSegment> segments,
                                  List<CatalogMediaAsset> mediaAssets, List<CatalogScene> scenes) {
        this.episode = episode;
        this.segments = segments;
        this.mediaAssets = mediaAssets;
        this.scenes = scenes;
    }

    public CatalogEpisode getEpisode() { return episode; }
    public void setEpisode(CatalogEpisode episode) { this.episode = episode; }

    public List<CatalogSegment> getSegments() { return segments; }
    public void setSegments(List<CatalogSegment> segments) { this.segments = segments; }

    public List<CatalogMediaAsset> getMediaAssets() { return mediaAssets; }
    public void setMediaAssets(List<CatalogMediaAsset> mediaAssets) { this.mediaAssets = mediaAssets; }

    public List<CatalogScene> getScenes() { return scenes; }
    public void setScenes(List<CatalogScene> scenes) { this.scenes = scenes; }
}
