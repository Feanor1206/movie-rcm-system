package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogMediaAsset;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface CatalogMediaAssetRepository extends JpaRepository<CatalogMediaAsset, String> {
    List<CatalogMediaAsset> findByEnabledTrue();
}
