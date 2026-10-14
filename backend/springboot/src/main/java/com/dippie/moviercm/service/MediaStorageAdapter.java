package com.dippie.moviercm.service;

import org.springframework.core.io.Resource;

import java.nio.file.Path;

public interface MediaStorageAdapter {

    String getProviderName();

    boolean isAvailable();

    Path resolveValidatedPath(String relativePath);

    Resource getResource(String relativePath);

    long getResourceLength(String relativePath);
}
