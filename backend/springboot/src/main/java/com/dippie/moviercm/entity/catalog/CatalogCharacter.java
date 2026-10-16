package com.dippie.moviercm.entity.catalog;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "catalog_characters")
public class CatalogCharacter {

    @Id
    @Column(length = 100)
    private String id;

    @Column(name = "series_ids_json", columnDefinition = "TEXT")
    private String seriesIdsJson;

    @Column(nullable = false, length = 255)
    private String name;

    @Column(name = "aliases_json", columnDefinition = "TEXT")
    private String aliasesJson;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Column(length = 50)
    private String role;

    @Column(name = "traits_json", columnDefinition = "TEXT")
    private String traitsJson;

    @Column(name = "relationships_json", columnDefinition = "TEXT")
    private String relationshipsJson;

    @Column(name = "voice_credits_json", columnDefinition = "TEXT")
    private String voiceCreditsJson;

    @Column(name = "artworks_json", columnDefinition = "TEXT")
    private String artworksJson;

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

    public CatalogCharacter() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getSeriesIdsJson() { return seriesIdsJson; }
    public void setSeriesIdsJson(String seriesIdsJson) { this.seriesIdsJson = seriesIdsJson; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getAliasesJson() { return aliasesJson; }
    public void setAliasesJson(String aliasesJson) { this.aliasesJson = aliasesJson; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }

    public String getTraitsJson() { return traitsJson; }
    public void setTraitsJson(String traitsJson) { this.traitsJson = traitsJson; }

    public String getRelationshipsJson() { return relationshipsJson; }
    public void setRelationshipsJson(String relationshipsJson) { this.relationshipsJson = relationshipsJson; }

    public String getVoiceCreditsJson() { return voiceCreditsJson; }
    public void setVoiceCreditsJson(String voiceCreditsJson) { this.voiceCreditsJson = voiceCreditsJson; }

    public String getArtworksJson() { return artworksJson; }
    public void setArtworksJson(String artworksJson) { this.artworksJson = artworksJson; }

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
