package com.dippie.moviercm.entity.catalog;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "catalog_text_tracks")
public class CatalogTextTrack {

    @Id
    @Column(length = 100)
    private String id;

    @Column(name = "media_asset_id", nullable = false, length = 100)
    private String mediaAssetId;

    @Column(nullable = false, length = 50)
    private String language;

    @Column(nullable = false, length = 50)
    private String kind;

    @Column(length = 255)
    private String label;

    @Column(nullable = false, length = 50)
    private String format;

    @Column(name = "is_default", nullable = false)
    private Boolean isDefault = false;

    @Column(name = "external_file_json", columnDefinition = "TEXT")
    private String externalFileJson;

    @Column(name = "cues_json", columnDefinition = "TEXT")
    private String cuesJson;

    @Column(name = "provenance_json", columnDefinition = "TEXT")
    private String provenanceJson;

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

    public CatalogTextTrack() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getMediaAssetId() { return mediaAssetId; }
    public void setMediaAssetId(String mediaAssetId) { this.mediaAssetId = mediaAssetId; }

    public String getLanguage() { return language; }
    public void setLanguage(String language) { this.language = language; }

    public String getKind() { return kind; }
    public void setKind(String kind) { this.kind = kind; }

    public String getLabel() { return label; }
    public void setLabel(String label) { this.label = label; }

    public String getFormat() { return format; }
    public void setFormat(String format) { this.format = format; }

    public Boolean getIsDefault() { return isDefault; }
    public void setIsDefault(Boolean isDefault) { this.isDefault = isDefault; }

    public String getExternalFileJson() { return externalFileJson; }
    public void setExternalFileJson(String externalFileJson) { this.externalFileJson = externalFileJson; }

    public String getCuesJson() { return cuesJson; }
    public void setCuesJson(String cuesJson) { this.cuesJson = cuesJson; }

    public String getProvenanceJson() { return provenanceJson; }
    public void setProvenanceJson(String provenanceJson) { this.provenanceJson = provenanceJson; }

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
