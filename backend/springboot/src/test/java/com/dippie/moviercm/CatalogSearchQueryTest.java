package com.dippie.moviercm;

import com.dippie.moviercm.dto.catalog.CatalogSearchResult;
import com.dippie.moviercm.service.catalog.CatalogQueryService;
import com.dippie.moviercm.service.catalog.CatalogSyncWorker;
import jakarta.persistence.EntityManagerFactory;
import org.hibernate.SessionFactory;
import org.hibernate.stat.Statistics;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(properties = "spring.jpa.properties.hibernate.generate_statistics=true")
@ActiveProfiles("test")
class CatalogSearchQueryTest {
    @Autowired CatalogQueryService service;
    @Autowired JdbcTemplate jdbc;
    @Autowired EntityManagerFactory entityManagerFactory;
    @MockBean CatalogSyncWorker syncWorker;

    @AfterEach
    void cleanup() {
        SecurityContextHolder.clearContext();
        jdbc.update("delete from catalog_scenes where id like 'search-%'");
        jdbc.update("delete from catalog_segments where id like 'search-%'");
        jdbc.update("delete from catalog_episodes where id like 'search-%'");
        jdbc.update("delete from catalog_media_assets where id like 'search-%'");
        jdbc.update("delete from catalog_series where id like 'search-%'");
    }

    @Test
    void searchKeepsVisibleResultsAndUsesBoundedQueries() {
        String ready = "{\"status\":\"ready\"}";
        jdbc.update("insert into catalog_series (id,title,record_json,revision) values (?,?,?,1)", "search-series", "Needle series", ready);
        for (int i = 0; i < 4; i++) {
            jdbc.update("insert into catalog_episodes (id,series_id,title,kind,record_json,revision) values (?,?,?,?,?,1)", "search-ep" + i, "search-series", "Needle episode " + i, "episode", ready);
            jdbc.update("insert into catalog_segments (id,episode_id,position,title,episode_start_ms,episode_end_ms,record_json,revision) values (?,?,?,?,?,?,?,1)", "search-seg" + i, "search-ep" + i, i, "Needle segment " + i, 10L, 20L, ready);
            jdbc.update("insert into catalog_scenes (id,episode_id,media_asset_id,start_ms,end_ms,title,record_json,revision) values (?,?,?,?,?,?,?,1)", "search-scene" + i, "search-ep" + i, "search-asset" + i, 30L, 40L, "Needle scene " + i, ready);
            jdbc.update("insert into catalog_media_assets (id,content_type,role,storage_provider,storage_key,relative_path,access_policy,enabled,revision) values (?,?,?,?,?,?,?,?,1)", "search-asset" + i, "video", "feature", "local", "key" + i, "path", i == 3 ? "private" : "public", true);
        }
        Statistics stats = entityManagerFactory.unwrap(SessionFactory.class).getStatistics();
        stats.clear();
        List<CatalogSearchResult> results = service.searchCatalog("Needle");
        long queryCount = stats.getPrepareStatementCount();
        System.out.println("Catalog search statements: " + queryCount);
        assertThat(results).extracting(CatalogSearchResult::getId).containsExactly(
                "search-series", "search-ep0", "search-ep1", "search-ep2", "search-ep3",
                "search-seg0", "search-seg1", "search-seg2", "search-seg3",
                "search-scene0", "search-scene1", "search-scene2");
        assertThat(results.get(5).getParentTitle()).isEqualTo("Needle episode 0");
        assertThat(results.get(5).getStartMs()).isEqualTo(10L);
        assertThat(results.get(9).getEndMs()).isEqualTo(40L);
        assertThat(queryCount).isLessThanOrEqualTo(7);

        jdbc.update("insert into catalog_segments (id,episode_id,position,title,record_json,revision) values (?,?,?,?,?,1)", "search-missing", "absent", 9, "Needle orphan", ready);
        jdbc.update("insert into catalog_scenes (id,episode_id,media_asset_id,start_ms,end_ms,title,record_json,revision) values (?,?,?,?,?,?,?,1)", "search-missing-asset", "search-ep0", "absent", 50L, 60L, "Needle missing asset", ready);
        assertThat(service.searchCatalog("Needle")).extracting(CatalogSearchResult::getId)
                .contains("search-missing-asset").doesNotContain("search-missing");
        SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(
                "admin", "", List.of(new SimpleGrantedAuthority("ROLE_ADMIN"))));
        List<CatalogSearchResult> adminResults = service.searchCatalog("Needle");
        assertThat(adminResults).extracting(CatalogSearchResult::getId)
                .contains("search-missing", "search-scene3", "search-missing-asset");
        assertThat(adminResults.stream().filter(result -> result.getId().equals("search-missing"))
                .findFirst().orElseThrow().getParentTitle()).isEqualTo("absent");
    }
}
