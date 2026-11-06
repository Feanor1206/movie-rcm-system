package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogSeries;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface CatalogSeriesRepository extends JpaRepository<CatalogSeries, String> {

    @Query("SELECT s FROM CatalogSeries s WHERE LOWER(s.title) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(s.originalTitle) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(s.aliasesJson) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(s.synopsis) LIKE LOWER(CONCAT('%', :q, '%'))")
    List<CatalogSeries> searchSeries(@Param("q") String query);

    List<CatalogSeries> findByReleaseYearStart(Integer releaseYearStart);
}
