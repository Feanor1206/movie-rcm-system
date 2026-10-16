package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogScene;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface CatalogSceneRepository extends JpaRepository<CatalogScene, String> {

    List<CatalogScene> findByEpisodeIdOrderByStartMsAsc(String episodeId);

    List<CatalogScene> findByMediaAssetIdOrderByStartMsAsc(String mediaAssetId);

    @Query("SELECT sc FROM CatalogScene sc WHERE LOWER(sc.title) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(sc.summary) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(sc.visualDescription) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(sc.keywordsJson) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(sc.themesJson) LIKE LOWER(CONCAT('%', :q, '%'))")
    List<CatalogScene> searchScenes(@Param("q") String query);
}
