package com.dippie.moviercm.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class MediaAssetDto {

    private String assetId;
    private String kind;
    private String streamUrl;
    private String mimeType;
    private Long byteLength;
    private Double durationSeconds;

    @JsonProperty("isPublic")
    private Boolean isPublic;

    private String version;

    public MediaAssetDto() {}

    public MediaAssetDto(String assetId, String kind, String streamUrl, String mimeType,
                         Long byteLength, Double durationSeconds, Boolean isPublic, String version) {
        this.assetId = assetId;
        this.kind = kind;
        this.streamUrl = streamUrl;
        this.mimeType = mimeType;
        this.byteLength = byteLength;
        this.durationSeconds = durationSeconds;
        this.isPublic = isPublic;
        this.version = version;
    }

    public String getAssetId() {
        return assetId;
    }

    public void setAssetId(String assetId) {
        this.assetId = assetId;
    }

    public String getKind() {
        return kind;
    }

    public void setKind(String kind) {
        this.kind = kind;
    }

    public String getStreamUrl() {
        return streamUrl;
    }

    public void setStreamUrl(String streamUrl) {
        this.streamUrl = streamUrl;
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

    @JsonProperty("isPublic")
    public Boolean getIsPublic() {
        return isPublic;
    }

    @JsonProperty("isPublic")
    public void setIsPublic(Boolean isPublic) {
        this.isPublic = isPublic;
    }

    @com.fasterxml.jackson.annotation.JsonIgnore
    public Boolean getPublic() {
        return isPublic;
    }

    @com.fasterxml.jackson.annotation.JsonIgnore
    public void setPublic(Boolean aPublic) {
        isPublic = aPublic;
    }

    public String getVersion() {
        return version;
    }

    public void setVersion(String version) {
        this.version = version;
    }
}
