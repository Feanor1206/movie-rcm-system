package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogGenre;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface CatalogGenreRepository extends JpaRepository<CatalogGenre, String> {
}
