package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogCharacter;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface CatalogCharacterRepository extends JpaRepository<CatalogCharacter, String> {

    @Query("SELECT c FROM CatalogCharacter c WHERE LOWER(c.name) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(c.aliasesJson) LIKE LOWER(CONCAT('%', :q, '%')) OR LOWER(c.description) LIKE LOWER(CONCAT('%', :q, '%'))")
    List<CatalogCharacter> searchCharacters(@Param("q") String query);
}
