package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogSegment;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface CatalogSegmentRepository extends JpaRepository<CatalogSegment, String> {

    List<CatalogSegment> findByEpisodeIdOrderByPositionAsc(String episodeId);

    @Query("SELECT s FROM CatalogSegment s WHERE LOWER(s.title) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(s.aliasesJson) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(s.synopsis) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(s.plotFactsJson) LIKE LOWER(CONCAT('%', :q, '%'))")
    List<CatalogSegment> searchSegments(@Param("q") String query);
}
