package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogPackage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface CatalogPackageRepository extends JpaRepository<CatalogPackage, String> {
    Optional<CatalogPackage> findFirstByOrderByImportedAtDesc();
}
