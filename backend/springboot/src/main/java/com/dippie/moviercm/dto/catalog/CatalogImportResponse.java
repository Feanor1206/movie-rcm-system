package com.dippie.moviercm.dto.catalog;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

public class CatalogImportResponse {
    private boolean success;
    private String importId;
    private String packageId;
    private Integer revision;
    private String contentHash;
    private LocalDateTime importedAt;
    private Map<String, Integer> counts = new HashMap<>();
    private String indexStatus;
    private String message;

    public CatalogImportResponse() {}

    public boolean isSuccess() { return success; }
    public void setSuccess(boolean success) { this.success = success; }

    public String getImportId() { return importId; }
    public void setImportId(String importId) { this.importId = importId; }

    public String getPackageId() { return packageId; }
    public void setPackageId(String packageId) { this.packageId = packageId; }

    public Integer getRevision() { return revision; }
    public void setRevision(Integer revision) { this.revision = revision; }

    public String getContentHash() { return contentHash; }
    public void setContentHash(String contentHash) { this.contentHash = contentHash; }

    public LocalDateTime getImportedAt() { return importedAt; }
    public void setImportedAt(LocalDateTime importedAt) { this.importedAt = importedAt; }

    public Map<String, Integer> getCounts() { return counts; }
    public void setCounts(Map<String, Integer> counts) { this.counts = counts; }

    public String getIndexStatus() { return indexStatus; }
    public void setIndexStatus(String indexStatus) { this.indexStatus = indexStatus; }

    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
}
