package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogSource;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface CatalogSourceRepository extends JpaRepository<CatalogSource, String> {
}
