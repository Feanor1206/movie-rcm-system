package com.dippie.moviercm.repository;

import com.dippie.moviercm.entity.WatchProgress;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface WatchProgressRepository extends JpaRepository<WatchProgress, Long> {
    List<WatchProgress> findTop30ByUserIdOrderByUpdatedAtDesc(Long userId);
    Optional<WatchProgress> findByUserIdAndEpisodeId(Long userId, String episodeId);
    void deleteByUserIdAndEpisodeId(Long userId, String episodeId);
    void deleteByUserId(Long userId);
}
