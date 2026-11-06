package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogEpisode;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface CatalogEpisodeRepository extends JpaRepository<CatalogEpisode, String> {

    List<CatalogEpisode> findBySeriesIdOrderByNumberAsc(String seriesId);

    List<CatalogEpisode> findBySeasonIdOrderByNumberAsc(String seasonId);

    @Query("SELECT e FROM CatalogEpisode e WHERE LOWER(e.title) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(e.aliasesJson) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(e.synopsis) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(e.plotFactsJson) LIKE LOWER(CONCAT('%', :q, '%'))")
    List<CatalogEpisode> searchEpisodes(@Param("q") String query);
}
