package com.dippie.moviercm.entity.catalog;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "catalog_attribute_scales")
public class CatalogAttributeScale {

    @Id
    @Column(length = 100)
    private String id;

    @Column(nullable = false, length = 255)
    private String name;

    @Column(columnDefinition = "TEXT")
    private String definition;

    @Column(nullable = false)
    private Double minimum;

    @Column(nullable = false)
    private Double maximum;

    @Column(name = "levels_json", nullable = false, columnDefinition = "TEXT")
    private String levelsJson;

    @Column(length = 50)
    private String version;

    @Column(name = "source_ids_json", columnDefinition = "TEXT")
    private String sourceIdsJson;

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

    public CatalogAttributeScale() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getDefinition() { return definition; }
    public void setDefinition(String definition) { this.definition = definition; }

    public Double getMinimum() { return minimum; }
    public void setMinimum(Double minimum) { this.minimum = minimum; }

    public Double getMaximum() { return maximum; }
    public void setMaximum(Double maximum) { this.maximum = maximum; }

    public String getLevelsJson() { return levelsJson; }
    public void setLevelsJson(String levelsJson) { this.levelsJson = levelsJson; }

    public String getVersion() { return version; }
    public void setVersion(String version) { this.version = version; }

    public String getSourceIdsJson() { return sourceIdsJson; }
    public void setSourceIdsJson(String sourceIdsJson) { this.sourceIdsJson = sourceIdsJson; }

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
