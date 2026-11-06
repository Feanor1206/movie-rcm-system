package com.dippie.moviercm.entity.catalog;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "catalog_episodes")
public class CatalogEpisode {

    @Id
    @Column(length = 100)
    private String id;

    @Column(name = "series_id", nullable = false, length = 100)
    private String seriesId;

    @Column(name = "season_id", length = 100)
    private String seasonId;

    @Column
    private Integer number;

    @Column(nullable = false, length = 255)
    private String title;

    @Column(name = "aliases_json", columnDefinition = "TEXT")
    private String aliasesJson;

    @Column(columnDefinition = "TEXT")
    private String synopsis;

    @Column(name = "translations_json", columnDefinition = "TEXT")
    private String translationsJson;

    @Column(nullable = false, length = 50)
    private String kind;

    @Column(name = "release_date", length = 50)
    private String releaseDate;

    @Column(name = "duration_ms")
    private Long durationMs;

    @Column(name = "genre_ids_json", columnDefinition = "TEXT")
    private String genreIdsJson;

    @Column(name = "primary_language", length = 50)
    private String primaryLanguage;

    @Column(name = "orders_json", columnDefinition = "TEXT")
    private String ordersJson;

    @Column(name = "links_json", columnDefinition = "TEXT")
    private String linksJson;

    @Column(name = "character_ids_json", columnDefinition = "TEXT")
    private String characterIdsJson;

    @Column(name = "plot_facts_json", columnDefinition = "TEXT")
    private String plotFactsJson;

    @Column(name = "keywords_json", columnDefinition = "TEXT")
    private String keywordsJson;

    @Column(name = "themes_json", columnDefinition = "TEXT")
    private String themesJson;

    @Column(name = "attributes_json", columnDefinition = "TEXT")
    private String attributesJson;

    @Column(name = "ratings_json", columnDefinition = "TEXT")
    private String ratingsJson;

    @Column(name = "artworks_json", columnDefinition = "TEXT")
    private String artworksJson;

    @Column(name = "credits_json", columnDefinition = "TEXT")
    private String creditsJson;

    @Column(name = "record_json", columnDefinition = "TEXT")
    private String recordJson;

    @Column(name = "raw_json", columnDefinition = "TEXT")
    private String rawJson;

    @Column(nullable = false)
    private Integer revision = 1;

    @Version
    @Column(name = "opt_lock_version")
    private Long optLockVersion = 0L;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt = LocalDateTime.now();

    public CatalogEpisode() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getSeriesId() { return seriesId; }
    public void setSeriesId(String seriesId) { this.seriesId = seriesId; }

    public String getSeasonId() { return seasonId; }
    public void setSeasonId(String seasonId) { this.seasonId = seasonId; }

    public Integer getNumber() { return number; }
    public void setNumber(Integer number) { this.number = number; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getAliasesJson() { return aliasesJson; }
    public void setAliasesJson(String aliasesJson) { this.aliasesJson = aliasesJson; }

    public String getSynopsis() { return synopsis; }
    public void setSynopsis(String synopsis) { this.synopsis = synopsis; }

    public String getTranslationsJson() { return translationsJson; }
    public void setTranslationsJson(String translationsJson) { this.translationsJson = translationsJson; }

    public String getKind() { return kind; }
    public void setKind(String kind) { this.kind = kind; }

    public String getReleaseDate() { return releaseDate; }
    public void setReleaseDate(String releaseDate) { this.releaseDate = releaseDate; }

    public Long getDurationMs() { return durationMs; }
    public void setDurationMs(Long durationMs) { this.durationMs = durationMs; }

    public String getGenreIdsJson() { return genreIdsJson; }
    public void setGenreIdsJson(String genreIdsJson) { this.genreIdsJson = genreIdsJson; }

    public String getPrimaryLanguage() { return primaryLanguage; }
    public void setPrimaryLanguage(String primaryLanguage) { this.primaryLanguage = primaryLanguage; }

    public String getOrdersJson() { return ordersJson; }
    public void setOrdersJson(String ordersJson) { this.ordersJson = ordersJson; }

    public String getLinksJson() { return linksJson; }
    public void setLinksJson(String linksJson) { this.linksJson = linksJson; }

    public String getCharacterIdsJson() { return characterIdsJson; }
    public void setCharacterIdsJson(String characterIdsJson) { this.characterIdsJson = characterIdsJson; }

    public String getPlotFactsJson() { return plotFactsJson; }
    public void setPlotFactsJson(String plotFactsJson) { this.plotFactsJson = plotFactsJson; }

    public String getKeywordsJson() { return keywordsJson; }
    public void setKeywordsJson(String keywordsJson) { this.keywordsJson = keywordsJson; }

    public String getThemesJson() { return themesJson; }
    public void setThemesJson(String themesJson) { this.themesJson = themesJson; }

    public String getAttributesJson() { return attributesJson; }
    public void setAttributesJson(String attributesJson) { this.attributesJson = attributesJson; }

    public String getRatingsJson() { return ratingsJson; }
    public void setRatingsJson(String ratingsJson) { this.ratingsJson = ratingsJson; }

    public String getArtworksJson() { return artworksJson; }
    public void setArtworksJson(String artworksJson) { this.artworksJson = artworksJson; }

    public String getCreditsJson() { return creditsJson; }
    public void setCreditsJson(String creditsJson) { this.creditsJson = creditsJson; }

    public String getRecordJson() { return recordJson; }
    public void setRecordJson(String recordJson) { this.recordJson = recordJson; }

    public String getRawJson() { return rawJson; }
    public void setRawJson(String rawJson) { this.rawJson = rawJson; }

    public Integer getRevision() { return revision; }
    public void setRevision(Integer revision) { this.revision = revision; }

    public Long getOptLockVersion() { return optLockVersion; }
    public void setOptLockVersion(Long optLockVersion) { this.optLockVersion = optLockVersion; }

    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
