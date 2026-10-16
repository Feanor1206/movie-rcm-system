package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogTextTrack;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface CatalogTextTrackRepository extends JpaRepository<CatalogTextTrack, String> {
    List<CatalogTextTrack> findByMediaAssetId(String mediaAssetId);
}
