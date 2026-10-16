package com.dippie.moviercm.entity.catalog;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "catalog_scenes")
public class CatalogScene {

    @Id
    @Column(length = 100)
    private String id;

    @Column(name = "media_asset_id", length = 100)
    private String mediaAssetId;

    @Column(name = "episode_id", nullable = false, length = 100)
    private String episodeId;

    @Column(name = "segment_id", length = 100)
    private String segmentId;

    @Column(name = "start_ms", nullable = false)
    private Long startMs;

    @Column(name = "end_ms", nullable = false)
    private Long endMs;

    @Column(length = 255)
    private String title;

    @Column(columnDefinition = "TEXT")
    private String summary;

    @Column(name = "visual_description", columnDefinition = "TEXT")
    private String visualDescription;

    @Column(name = "visual_tags_json", columnDefinition = "TEXT")
    private String visualTagsJson;

    @Column(name = "sound_events_json", columnDefinition = "TEXT")
    private String soundEventsJson;

    @Column(name = "transcript_cue_ids_json", columnDefinition = "TEXT")
    private String transcriptCueIdsJson;

    @Column(name = "character_ids_json", columnDefinition = "TEXT")
    private String characterIdsJson;

    @Column(name = "keywords_json", columnDefinition = "TEXT")
    private String keywordsJson;

    @Column(name = "themes_json", columnDefinition = "TEXT")
    private String themesJson;

    @Column(name = "attributes_json", columnDefinition = "TEXT")
    private String attributesJson;

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

    public CatalogScene() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getMediaAssetId() { return mediaAssetId; }
    public void setMediaAssetId(String mediaAssetId) { this.mediaAssetId = mediaAssetId; }

    public String getEpisodeId() { return episodeId; }
    public void setEpisodeId(String episodeId) { this.episodeId = episodeId; }

    public String getSegmentId() { return segmentId; }
    public void setSegmentId(String segmentId) { this.segmentId = segmentId; }

    public Long getStartMs() { return startMs; }
    public void setStartMs(Long startMs) { this.startMs = startMs; }

    public Long getEndMs() { return endMs; }
    public void setEndMs(Long endMs) { this.endMs = endMs; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getSummary() { return summary; }
    public void setSummary(String summary) { this.summary = summary; }

    public String getVisualDescription() { return visualDescription; }
    public void setVisualDescription(String visualDescription) { this.visualDescription = visualDescription; }

    public String getVisualTagsJson() { return visualTagsJson; }
    public void setVisualTagsJson(String visualTagsJson) { this.visualTagsJson = visualTagsJson; }

    public String getSoundEventsJson() { return soundEventsJson; }
    public void setSoundEventsJson(String soundEventsJson) { this.soundEventsJson = soundEventsJson; }

    public String getTranscriptCueIdsJson() { return transcriptCueIdsJson; }
    public void setTranscriptCueIdsJson(String transcriptCueIdsJson) { this.transcriptCueIdsJson = transcriptCueIdsJson; }

    public String getCharacterIdsJson() { return characterIdsJson; }
    public void setCharacterIdsJson(String characterIdsJson) { this.characterIdsJson = characterIdsJson; }

    public String getKeywordsJson() { return keywordsJson; }
    public void setKeywordsJson(String keywordsJson) { this.keywordsJson = keywordsJson; }

    public String getThemesJson() { return themesJson; }
    public void setThemesJson(String themesJson) { this.themesJson = themesJson; }

    public String getAttributesJson() { return attributesJson; }
    public void setAttributesJson(String attributesJson) { this.attributesJson = attributesJson; }

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
