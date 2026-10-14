package com.dippie.moviercm.service;

import com.dippie.moviercm.exception.MediaUnavailableException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Component;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

@Component("driveStorageAdapter")
public class DriveMediaStorageAdapter implements MediaStorageAdapter {

    private final String driveMountPath;

    public DriveMediaStorageAdapter(@Value("${app.media.drive-mount:}") String driveMountPath) {
        this.driveMountPath = driveMountPath;
    }

    @Override
    public String getProviderName() {
        return "drive";
    }

    @Override
    public boolean isAvailable() {
        if (driveMountPath == null || driveMountPath.trim().isEmpty()) {
            return false;
        }
        try {
            Path path = Paths.get(driveMountPath);
            return Files.exists(path) && Files.isDirectory(path) && Files.isReadable(path);
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    public Path resolveValidatedPath(String relativePath) {
        throw new MediaUnavailableException(
            "Dịch vụ lưu trữ Google Drive chưa sẵn sàng (BLOCKED_EXTERNAL_INPUT: rclone/WinFsp chưa được cấu hình)"
        );
    }

    @Override
    public Resource getResource(String relativePath) {
        throw new MediaUnavailableException(
            "Dịch vụ lưu trữ Google Drive chưa sẵn sàng (BLOCKED_EXTERNAL_INPUT: rclone/WinFsp chưa được cấu hình)"
        );
    }

    @Override
    public long getResourceLength(String relativePath) {
        throw new MediaUnavailableException(
            "Dịch vụ lưu trữ Google Drive chưa sẵn sàng (BLOCKED_EXTERNAL_INPUT: rclone/WinFsp chưa được cấu hình)"
        );
    }
}
