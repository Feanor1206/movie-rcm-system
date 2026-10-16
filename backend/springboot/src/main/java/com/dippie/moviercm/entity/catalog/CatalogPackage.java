package com.dippie.moviercm.entity.catalog;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "catalog_packages")
public class CatalogPackage {

    @Id
    @Column(length = 100)
    private String id;

    @Column(nullable = false, length = 50)
    private String version;

    @Column(nullable = false)
    private Integer revision;

    @Column(name = "default_language", nullable = false, length = 20)
    private String defaultLanguage;

    @Column(name = "import_mode", nullable = false, length = 50)
    private String importMode;

    @Column(name = "reference_scope", nullable = false, length = 50)
    private String referenceScope;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Column(name = "content_hash", nullable = false, length = 100)
    private String contentHash;

    @Column(nullable = false, length = 50)
    private String status;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Version
    @Column(name = "opt_lock_version")
    private Long optLockVersion = 0L;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "imported_at")
    private LocalDateTime importedAt = LocalDateTime.now();

    public CatalogPackage() {}

    public CatalogPackage(String id, String version, Integer revision, String defaultLanguage,
                          String importMode, String referenceScope, String contentHash,
                          String status, String errorMessage, LocalDateTime createdAt) {
        this.id = id;
        this.version = version;
        this.revision = revision;
        this.defaultLanguage = defaultLanguage;
        this.importMode = importMode;
        this.referenceScope = referenceScope;
        this.contentHash = contentHash;
        this.status = status;
        this.errorMessage = errorMessage;
        this.createdAt = createdAt;
        this.importedAt = LocalDateTime.now();
    }

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getVersion() { return version; }
    public void setVersion(String version) { this.version = version; }

    public Integer getRevision() { return revision; }
    public void setRevision(Integer revision) { this.revision = revision; }

    public String getDefaultLanguage() { return defaultLanguage; }
    public void setDefaultLanguage(String defaultLanguage) { this.defaultLanguage = defaultLanguage; }

    public String getImportMode() { return importMode; }
    public void setImportMode(String importMode) { this.importMode = importMode; }

    public String getReferenceScope() { return referenceScope; }
    public void setReferenceScope(String referenceScope) { this.referenceScope = referenceScope; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public String getContentHash() { return contentHash; }
    public void setContentHash(String contentHash) { this.contentHash = contentHash; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }

    public Long getOptLockVersion() { return optLockVersion; }
    public void setOptLockVersion(Long optLockVersion) { this.optLockVersion = optLockVersion; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    public LocalDateTime getImportedAt() { return importedAt; }
    public void setImportedAt(LocalDateTime importedAt) { this.importedAt = importedAt; }
}
