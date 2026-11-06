package com.dippie.moviercm.repository;

import com.dippie.moviercm.entity.MediaAsset;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface MediaAssetRepository extends JpaRepository<MediaAsset, String> {

    List<MediaAsset> findByMovieId(String movieId);

    List<MediaAsset> findByMovieIdAndIsAvailableTrue(String movieId);

    Optional<MediaAsset> findFirstByMovieIdAndKindAndIsAvailableTrueOrderByCreatedAtDesc(String movieId, String kind);

    Optional<MediaAsset> findByIdAndIsAvailableTrue(String id);
}
