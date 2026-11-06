package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogSeason;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface CatalogSeasonRepository extends JpaRepository<CatalogSeason, String> {
    List<CatalogSeason> findBySeriesIdOrderByNumberAsc(String seriesId);
}
