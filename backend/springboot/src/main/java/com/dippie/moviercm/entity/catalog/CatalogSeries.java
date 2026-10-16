package com.dippie.moviercm.entity.catalog;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "catalog_series")
public class CatalogSeries {

    @Id
    @Column(length = 100)
    private String id;

    @Column(nullable = false, length = 255)
    private String title;

    @Column(name = "original_title", length = 255)
    private String originalTitle;

    @Column(name = "aliases_json", columnDefinition = "TEXT")
    private String aliasesJson;

    @Column(columnDefinition = "TEXT")
    private String synopsis;

    @Column(name = "translations_json", columnDefinition = "TEXT")
    private String translationsJson;

    @Column(name = "genre_ids_json", columnDefinition = "TEXT")
    private String genreIdsJson;

    @Column(name = "keywords_json", columnDefinition = "TEXT")
    private String keywordsJson;

    @Column(name = "themes_json", columnDefinition = "TEXT")
    private String themesJson;

    @Column(name = "origin_countries_json", columnDefinition = "TEXT")
    private String originCountriesJson;

    @Column(name = "original_languages_json", columnDefinition = "TEXT")
    private String originalLanguagesJson;

    @Column(name = "release_year_start")
    private Integer releaseYearStart;

    @Column(name = "release_year_end")
    private Integer releaseYearEnd;

    @Column(name = "release_status", length = 50)
    private String releaseStatus;

    @Column(name = "character_ids_json", columnDefinition = "TEXT")
    private String characterIdsJson;

    @Column(name = "artworks_json", columnDefinition = "TEXT")
    private String artworksJson;

    @Column(name = "attributes_json", columnDefinition = "TEXT")
    private String attributesJson;

    @Column(name = "ratings_json", columnDefinition = "TEXT")
    private String ratingsJson;

    @Column(name = "advisories_json", columnDefinition = "TEXT")
    private String advisoriesJson;

    @Column(name = "credits_json", columnDefinition = "TEXT")
    private String creditsJson;

    @Column(name = "external_ids_json", columnDefinition = "TEXT")
    private String externalIdsJson;

    @Column(name = "record_json", columnDefinition = "TEXT")
    private String recordJson;

    @Column(name = "raw_json", columnDefinition = "TEXT")
    private String rawJson;

    @Column(nullable = false)
    private Integer revision = 1;

    @Version
    @Column(name = "opt_lock_version")
    private Long optLockVersion = 0L;

    @Column(name = "created_at")
    private LocalDateTime createdAt = LocalDateTime.now();

    @Column(name = "updated_at")
    private LocalDateTime updatedAt = LocalDateTime.now();

    public CatalogSeries() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getOriginalTitle() { return originalTitle; }
    public void setOriginalTitle(String originalTitle) { this.originalTitle = originalTitle; }

    public String getAliasesJson() { return aliasesJson; }
    public void setAliasesJson(String aliasesJson) { this.aliasesJson = aliasesJson; }

    public String getSynopsis() { return synopsis; }
    public void setSynopsis(String synopsis) { this.synopsis = synopsis; }

    public String getTranslationsJson() { return translationsJson; }
    public void setTranslationsJson(String translationsJson) { this.translationsJson = translationsJson; }

    public String getGenreIdsJson() { return genreIdsJson; }
    public void setGenreIdsJson(String genreIdsJson) { this.genreIdsJson = genreIdsJson; }

    public String getKeywordsJson() { return keywordsJson; }
    public void setKeywordsJson(String keywordsJson) { this.keywordsJson = keywordsJson; }

    public String getThemesJson() { return themesJson; }
    public void setThemesJson(String themesJson) { this.themesJson = themesJson; }

    public String getOriginCountriesJson() { return originCountriesJson; }
    public void setOriginCountriesJson(String originCountriesJson) { this.originCountriesJson = originCountriesJson; }

    public String getOriginalLanguagesJson() { return originalLanguagesJson; }
    public void setOriginalLanguagesJson(String originalLanguagesJson) { this.originalLanguagesJson = originalLanguagesJson; }

    public Integer getReleaseYearStart() { return releaseYearStart; }
    public void setReleaseYearStart(Integer releaseYearStart) { this.releaseYearStart = releaseYearStart; }

    public Integer getReleaseYearEnd() { return releaseYearEnd; }
    public void setReleaseYearEnd(Integer releaseYearEnd) { this.releaseYearEnd = releaseYearEnd; }

    public String getReleaseStatus() { return releaseStatus; }
    public void setReleaseStatus(String releaseStatus) { this.releaseStatus = releaseStatus; }

    public String getCharacterIdsJson() { return characterIdsJson; }
    public void setCharacterIdsJson(String characterIdsJson) { this.characterIdsJson = characterIdsJson; }

    public String getArtworksJson() { return artworksJson; }
    public void setArtworksJson(String artworksJson) { this.artworksJson = artworksJson; }

    public String getAttributesJson() { return attributesJson; }
    public void setAttributesJson(String attributesJson) { this.attributesJson = attributesJson; }

    public String getRatingsJson() { return ratingsJson; }
    public void setRatingsJson(String ratingsJson) { this.ratingsJson = ratingsJson; }

    public String getAdvisoriesJson() { return advisoriesJson; }
    public void setAdvisoriesJson(String advisoriesJson) { this.advisoriesJson = advisoriesJson; }

    public String getCreditsJson() { return creditsJson; }
    public void setCreditsJson(String creditsJson) { this.creditsJson = creditsJson; }

    public String getExternalIdsJson() { return externalIdsJson; }
    public void setExternalIdsJson(String externalIdsJson) { this.externalIdsJson = externalIdsJson; }

    public String getRecordJson() { return recordJson; }
    public void setRecordJson(String recordJson) { this.recordJson = recordJson; }

    public String getRawJson() { return rawJson; }
    public void setRawJson(String rawJson) { this.rawJson = rawJson; }

    public Integer getRevision() { return revision; }
    public void setRevision(Integer revision) { this.revision = revision; }

    public Long getOptLockVersion() { return optLockVersion; }
    public void setOptLockVersion(Long optLockVersion) { this.optLockVersion = optLockVersion; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
