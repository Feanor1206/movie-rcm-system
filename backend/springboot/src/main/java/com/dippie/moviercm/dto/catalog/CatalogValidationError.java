package com.dippie.moviercm.dto.catalog;

public class CatalogValidationError {
    private String path;
    private String code;
    private String message;

    public CatalogValidationError() {}

    public CatalogValidationError(String path, String code, String message) {
        this.path = path;
        this.code = code;
        this.message = message;
    }

    public String getPath() { return path; }
    public void setPath(String path) { this.path = path; }

    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }

    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
}
