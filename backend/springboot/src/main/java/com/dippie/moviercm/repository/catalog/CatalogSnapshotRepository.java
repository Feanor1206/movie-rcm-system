package com.dippie.moviercm.repository.catalog;

import com.dippie.moviercm.entity.catalog.CatalogSnapshot;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface CatalogSnapshotRepository extends JpaRepository<CatalogSnapshot, String> {
    Optional<CatalogSnapshot> findTopByOrderBySnapshotVersionDesc();
    List<CatalogSnapshot> findByStatusInOrderBySnapshotVersionAsc(List<String> statuses);

    @Query("SELECT COALESCE(MAX(s.snapshotVersion), 0) FROM CatalogSnapshot s")
    Long findMaxSnapshotVersion();
}
