package com.dippie.moviercm.dto.catalog;

import java.util.ArrayList;
import java.util.List;

public class CatalogValidationResult {
    private boolean valid;
    private String packageId;
    private Integer revision;
    private String contentHash;
    private int toCreate;
    private int toUpdate;
    private int unchanged;
    private int conflicts;
    private List<CatalogValidationError> errors = new ArrayList<>();

    public CatalogValidationResult() {}

    public CatalogValidationResult(boolean valid, List<CatalogValidationError> errors) {
        this.valid = valid;
        this.errors = errors != null ? errors : new ArrayList<>();
    }

    public boolean isValid() { return valid; }
    public void setValid(boolean valid) { this.valid = valid; }

    public String getPackageId() { return packageId; }
    public void setPackageId(String packageId) { this.packageId = packageId; }

    public Integer getRevision() { return revision; }
    public void setRevision(Integer revision) { this.revision = revision; }

    public String getContentHash() { return contentHash; }
    public void setContentHash(String contentHash) { this.contentHash = contentHash; }

    public int getToCreate() { return toCreate; }
    public void setToCreate(int toCreate) { this.toCreate = toCreate; }

    public int getToUpdate() { return toUpdate; }
    public void setToUpdate(int toUpdate) { this.toUpdate = toUpdate; }

    public int getUnchanged() { return unchanged; }
    public void setUnchanged(int unchanged) { this.unchanged = unchanged; }

    public int getConflicts() { return conflicts; }
    public void setConflicts(int conflicts) { this.conflicts = conflicts; }

    public List<CatalogValidationError> getErrors() { return errors; }
    public void setErrors(List<CatalogValidationError> errors) { this.errors = errors; }
}
