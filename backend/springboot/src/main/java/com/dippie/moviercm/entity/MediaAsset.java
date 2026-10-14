package com.dippie.moviercm.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;

@Entity
@Table(
    name = "media_assets",
    uniqueConstraints = {
        @UniqueConstraint(name = "uq_movie_kind_version", columnNames = {"movie_id", "kind", "version"})
    },
    indexes = {
        @Index(name = "idx_media_movie_id", columnList = "movie_id"),
        @Index(name = "idx_media_movie_kind", columnList = "movie_id, kind")
    }
)
public class MediaAsset {

    @Id
    @Column(length = 64)
    private String id;

    @Column(name = "movie_id", nullable = false, length = 100)
    private String movieId;

    @Column(nullable = false, length = 20)
    private String kind; // "feature" or "trailer"

    @Column(name = "storage_provider", nullable = false, length = 30)
    private String storageProvider = "local";

    @Column(name = "relative_path", nullable = false, length = 500)
    private String relativePath;

    @Column(nullable = false, length = 50)
    private String version = "v1";

    @Column(name = "mime_type", nullable = false, length = 100)
    private String mimeType = "video/mp4";

    @Column(name = "byte_length", nullable = false)
    private Long byteLength;

    @Column(name = "duration_seconds")
    private Double durationSeconds;

    @Column(name = "is_public", nullable = false)
    private Boolean isPublic = true;

    @Column(name = "is_available", nullable = false)
    private Boolean isAvailable = true;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    public MediaAsset() {}

    public MediaAsset(String id, String movieId, String kind, String storageProvider,
                      String relativePath, String version, String mimeType,
                      Long byteLength, Double durationSeconds, Boolean isPublic, Boolean isAvailable) {
        this.id = id;
        this.movieId = movieId;
        this.kind = kind;
        this.storageProvider = storageProvider != null ? storageProvider : "local";
        this.relativePath = relativePath;
        this.version = version != null ? version : "v1";
        this.mimeType = mimeType != null ? mimeType : "video/mp4";
        this.byteLength = byteLength;
        this.durationSeconds = durationSeconds;
        this.isPublic = isPublic != null ? isPublic : true;
        this.isAvailable = isAvailable != null ? isAvailable : true;
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getMovieId() {
        return movieId;
    }

    public void setMovieId(String movieId) {
        this.movieId = movieId;
    }

    public String getKind() {
        return kind;
    }

    public void setKind(String kind) {
        this.kind = kind;
    }

    public String getStorageProvider() {
        return storageProvider;
    }

    public void setStorageProvider(String storageProvider) {
        this.storageProvider = storageProvider;
    }

    public String getRelativePath() {
        return relativePath;
    }

    public void setRelativePath(String relativePath) {
        this.relativePath = relativePath;
    }

    public String getVersion() {
        return version;
    }

    public void setVersion(String version) {
        this.version = version;
    }

    public String getMimeType() {
        return mimeType;
    }

    public void setMimeType(String mimeType) {
        this.mimeType = mimeType;
    }

    public Long getByteLength() {
        return byteLength;
    }

    public void setByteLength(Long byteLength) {
        this.byteLength = byteLength;
    }

    public Double getDurationSeconds() {
        return durationSeconds;
    }

    public void setDurationSeconds(Double durationSeconds) {
        this.durationSeconds = durationSeconds;
    }

    public Boolean getPublic() {
        return isPublic;
    }

    public void setPublic(Boolean aPublic) {
        isPublic = aPublic;
    }

    public Boolean getAvailable() {
        return isAvailable;
    }

    public void setAvailable(Boolean available) {
        isAvailable = available;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
}
