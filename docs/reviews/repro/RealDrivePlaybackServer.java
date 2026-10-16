// package com.dippie.moviercm.review;

import com.dippie.moviercm.MovieRcmApplication;
import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.servlet.context.ServletWebServerApplicationContext;
import java.nio.file.*;
import java.io.*;

/** Reviewer-only isolated H2 launcher. Never creates, copies or renames anything on Drive. */
public class RealDrivePlaybackServer {
  public static void main(String[] args) throws Exception {
    if (args.length != 2) throw new IllegalArgumentException("mountRoot localTempRoot");
    Path drive = Path.of(args[0]).toAbsolutePath().normalize();
    Path local = Path.of(args[1]).toAbsolutePath().normalize();
    if (local.startsWith(drive)) throw new IllegalArgumentException("Local fixture must be outside Drive");
    long size = Files.size(drive.resolve("videoplayback.mp4"));
    try (var ctx = new SpringApplicationBuilder(MovieRcmApplication.class).run(
      "--spring.profiles.active=test", "--server.address=127.0.0.1", "--server.port=0",
      "--spring.datasource.url=jdbc:h2:mem:codex_real_drive_" + System.nanoTime()
        + ";DB_CLOSE_DELAY=-1;MODE=PostgreSQL;NON_KEYWORDS=YEAR,USER",
      "--spring.jpa.hibernate.ddl-auto=create-drop", "--spring.sql.init.mode=never",
      "--app.seed.enabled=false", "--app.media.root=" + local,
      "--app.media.drive-mount=" + drive,
      "--app.media.drive-metadata-timeout-ms=15000",
      "--app.media.drive-read-timeout-ms=15000")) {
      ctx.getBean(MovieRepository.class).save(Movie.builder().id("codex-real-drive-video")
        .title("Drive uploaded video playback test").year(2026).rating(0.0)
        .runtime("").genres("Animation").description("User uploaded MP4; actual Drive mount test")
        .poster("").backdrop("").build());
      ctx.getBean(MediaAssetRepository.class).save(new MediaAsset("codex-real-drive-feature",
        "codex-real-drive-video", "feature", "drive", "videoplayback.mp4", "v1",
        "video/mp4", size, null, true, true));
      System.out.println("REAL_DRIVE_PORT=" + ((ServletWebServerApplicationContext)ctx).getWebServer().getPort());
      System.out.println("REAL_DRIVE_BYTES=" + size);
      System.out.flush();
      while (System.in.read() != -1) { /* owned launcher stops when parent closes stdin */ }
    }
  }
}
