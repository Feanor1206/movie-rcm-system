package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogAttributeScale;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface CatalogAttributeScaleRepository extends JpaRepository<CatalogAttributeScale, String> {
}
