package com.dippie.moviercm.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;

public class WatchProgressRequest {

    @NotBlank(message = "Asset ID is required")
    private String assetId;

    @NotNull(message = "Position is required")
    private BigDecimal positionMs;

    @NotNull(message = "Expected version is required")
    private Long expectedVersion;

    public WatchProgressRequest() {}

    public WatchProgressRequest(String assetId, BigDecimal positionMs, Long expectedVersion) {
        this.assetId = assetId;
        this.positionMs = positionMs;
        this.expectedVersion = expectedVersion;
    }

    public String getAssetId() { return assetId; }
    public void setAssetId(String assetId) { this.assetId = assetId; }
    public BigDecimal getPositionMs() { return positionMs; }
    public void setPositionMs(BigDecimal positionMs) { this.positionMs = positionMs; }
    public Long getExpectedVersion() { return expectedVersion; }
    public void setExpectedVersion(Long expectedVersion) { this.expectedVersion = expectedVersion; }
}
