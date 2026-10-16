package com.dippie.moviercm.dto.catalog;

import com.dippie.moviercm.entity.catalog.CatalogEpisode;
import com.dippie.moviercm.entity.catalog.CatalogSeason;
import com.dippie.moviercm.entity.catalog.CatalogSeries;

import java.util.List;

public class CatalogSeriesResponse {
    private CatalogSeries series;
    private List<CatalogSeason> seasons;
    private List<CatalogEpisode> episodes;

    public CatalogSeriesResponse() {}

    public CatalogSeriesResponse(CatalogSeries series, List<CatalogSeason> seasons, List<CatalogEpisode> episodes) {
        this.series = series;
        this.seasons = seasons;
        this.episodes = episodes;
    }

    public CatalogSeries getSeries() { return series; }
    public void setSeries(CatalogSeries series) { this.series = series; }

    public List<CatalogSeason> getSeasons() { return seasons; }
    public void setSeasons(List<CatalogSeason> seasons) { this.seasons = seasons; }

    public List<CatalogEpisode> getEpisodes() { return episodes; }
    public void setEpisodes(List<CatalogEpisode> episodes) { this.episodes = episodes; }
}
