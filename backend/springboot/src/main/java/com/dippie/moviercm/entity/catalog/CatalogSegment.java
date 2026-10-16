package com.dippie.moviercm.entity.catalog;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "catalog_segments")
public class CatalogSegment {

    @Id
    @Column(length = 100)
    private String id;

    @Column(name = "episode_id", nullable = false, length = 100)
    private String episodeId;

    @Column(nullable = false)
    private Integer position;

    @Column(nullable = false, length = 255)
    private String title;

    @Column(name = "aliases_json", columnDefinition = "TEXT")
    private String aliasesJson;

    @Column(columnDefinition = "TEXT")
    private String synopsis;

    @Column(name = "translations_json", columnDefinition = "TEXT")
    private String translationsJson;

    @Column(name = "primary_language", length = 50)
    private String primaryLanguage;

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

    @Column(name = "episode_start_ms")
    private Long episodeStartMs;

    @Column(name = "episode_end_ms")
    private Long episodeEndMs;

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

    public CatalogSegment() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getEpisodeId() { return episodeId; }
    public void setEpisodeId(String episodeId) { this.episodeId = episodeId; }

    public Integer getPosition() { return position; }
    public void setPosition(Integer position) { this.position = position; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getAliasesJson() { return aliasesJson; }
    public void setAliasesJson(String aliasesJson) { this.aliasesJson = aliasesJson; }

    public String getSynopsis() { return synopsis; }
    public void setSynopsis(String synopsis) { this.synopsis = synopsis; }

    public String getTranslationsJson() { return translationsJson; }
    public void setTranslationsJson(String translationsJson) { this.translationsJson = translationsJson; }

    public String getPrimaryLanguage() { return primaryLanguage; }
    public void setPrimaryLanguage(String primaryLanguage) { this.primaryLanguage = primaryLanguage; }

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

    public Long getEpisodeStartMs() { return episodeStartMs; }
    public void setEpisodeStartMs(Long episodeStartMs) { this.episodeStartMs = episodeStartMs; }

    public Long getEpisodeEndMs() { return episodeEndMs; }
    public void setEpisodeEndMs(Long episodeEndMs) { this.episodeEndMs = episodeEndMs; }

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
