package com.dippie.moviercm.entity.catalog;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "catalog_snapshots")
public class CatalogSnapshot {

    @Id
    @Column(length = 100)
    private String id;

    @Column(name = "snapshot_version", nullable = false, unique = true)
    private Long snapshotVersion;

    @Column(name = "content_hash", nullable = false, length = 100)
    private String contentHash;

    @Column(name = "total_items", nullable = false)
    private Integer totalItems;

    @Column(nullable = false, length = 50)
    private String status; // PENDING, SYNCING, READY, FAILED

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "retry_count")
    private Integer retryCount = 0;

    @Column(name = "created_at")
    private LocalDateTime createdAt = LocalDateTime.now();

    @Column(name = "completed_at")
    private LocalDateTime completedAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt = LocalDateTime.now();

    public CatalogSnapshot() {}

    public CatalogSnapshot(String id, Long snapshotVersion, String contentHash, Integer totalItems, String status) {
        this.id = id;
        this.snapshotVersion = snapshotVersion;
        this.contentHash = contentHash;
        this.totalItems = totalItems;
        this.status = status;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public Long getSnapshotVersion() { return snapshotVersion; }
    public void setSnapshotVersion(Long snapshotVersion) { this.snapshotVersion = snapshotVersion; }

    public String getContentHash() { return contentHash; }
    public void setContentHash(String contentHash) { this.contentHash = contentHash; }

    public Integer getTotalItems() { return totalItems; }
    public void setTotalItems(Integer totalItems) { this.totalItems = totalItems; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }

    public Integer getRetryCount() { return retryCount; }
    public void setRetryCount(Integer retryCount) { this.retryCount = retryCount; }

    public LocalDateTime getCompletedAt() { return completedAt; }
    public void setCompletedAt(LocalDateTime completedAt) { this.completedAt = completedAt; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
