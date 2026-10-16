package com.dippie.moviercm.entity.catalog;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "catalog_media_assets")
public class CatalogMediaAsset {

    @Id
    @Column(length = 100)
    private String id;

    @Column(name = "content_type", nullable = false, length = 50)
    private String contentType = "video";

    @Column(nullable = false, length = 50)
    private String role = "feature";

    @Column(name = "edition_label", length = 100)
    private String editionLabel;

    @Column(name = "spoken_languages_json", columnDefinition = "TEXT")
    private String spokenLanguagesJson;

    @Column(name = "embedded_subtitle_languages_json", columnDefinition = "TEXT")
    private String embeddedSubtitleLanguagesJson;

    @Column(name = "storage_provider", nullable = false, length = 50)
    private String storageProvider;

    @Column(name = "storage_key", nullable = false, length = 100)
    private String storageKey;

    @Column(name = "relative_path", nullable = false, length = 500)
    private String relativePath;

    @Column(name = "drive_file_id", length = 255)
    private String driveFileId;

    @Column(name = "drive_folder_id", length = 255)
    private String driveFolderId;

    @Column(name = "size_bytes")
    private Long sizeBytes;

    @Column(length = 100)
    private String sha256;

    @Column(name = "duration_ms")
    private Long durationMs;

    @Column(name = "technical_json", columnDefinition = "TEXT")
    private String technicalJson;

    @Column(name = "coverage_json", columnDefinition = "TEXT")
    private String coverageJson;

    @Column(name = "related_asset_id", length = 100)
    private String relatedAssetId;

    @Column(name = "access_policy", nullable = false, length = 50)
    private String accessPolicy = "public";

    @Column(nullable = false)
    private Boolean enabled = true;

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

    public CatalogMediaAsset() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getContentType() { return contentType; }
    public void setContentType(String contentType) { this.contentType = contentType; }

    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }

    public String getEditionLabel() { return editionLabel; }
    public void setEditionLabel(String editionLabel) { this.editionLabel = editionLabel; }

    public String getSpokenLanguagesJson() { return spokenLanguagesJson; }
    public void setSpokenLanguagesJson(String spokenLanguagesJson) { this.spokenLanguagesJson = spokenLanguagesJson; }

    public String getEmbeddedSubtitleLanguagesJson() { return embeddedSubtitleLanguagesJson; }
    public void setEmbeddedSubtitleLanguagesJson(String embeddedSubtitleLanguagesJson) { this.embeddedSubtitleLanguagesJson = embeddedSubtitleLanguagesJson; }

    public String getStorageProvider() { return storageProvider; }
    public void setStorageProvider(String storageProvider) { this.storageProvider = storageProvider; }

    public String getStorageKey() { return storageKey; }
    public void setStorageKey(String storageKey) { this.storageKey = storageKey; }

    public String getRelativePath() { return relativePath; }
    public void setRelativePath(String relativePath) { this.relativePath = relativePath; }

    public String getDriveFileId() { return driveFileId; }
    public void setDriveFileId(String driveFileId) { this.driveFileId = driveFileId; }

    public String getDriveFolderId() { return driveFolderId; }
    public void setDriveFolderId(String driveFolderId) { this.driveFolderId = driveFolderId; }

    public Long getSizeBytes() { return sizeBytes; }
    public void setSizeBytes(Long sizeBytes) { this.sizeBytes = sizeBytes; }

    public String getSha256() { return sha256; }
    public void setSha256(String sha256) { this.sha256 = sha256; }

    public Long getDurationMs() { return durationMs; }
    public void setDurationMs(Long durationMs) { this.durationMs = durationMs; }

    public String getTechnicalJson() { return technicalJson; }
    public void setTechnicalJson(String technicalJson) { this.technicalJson = technicalJson; }

    public String getCoverageJson() { return coverageJson; }
    public void setCoverageJson(String coverageJson) { this.coverageJson = coverageJson; }

    public String getRelatedAssetId() { return relatedAssetId; }
    public void setRelatedAssetId(String relatedAssetId) { this.relatedAssetId = relatedAssetId; }

    public String getAccessPolicy() { return accessPolicy; }
    public void setAccessPolicy(String accessPolicy) { this.accessPolicy = accessPolicy; }

    public Boolean getEnabled() { return enabled; }
    public void setEnabled(Boolean enabled) { this.enabled = enabled; }

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
