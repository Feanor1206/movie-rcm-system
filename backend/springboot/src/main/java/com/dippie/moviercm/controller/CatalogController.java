package com.dippie.moviercm.controller;

import com.dippie.moviercm.dto.catalog.CatalogEpisodeResponse;
import com.dippie.moviercm.dto.catalog.CatalogSearchResult;
import com.dippie.moviercm.dto.catalog.CatalogSeriesResponse;
import com.dippie.moviercm.entity.catalog.CatalogSeries;
import com.dippie.moviercm.service.catalog.CatalogQueryService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/catalog")
public class CatalogController {

    private final CatalogQueryService queryService;

    @Autowired
    public CatalogController(CatalogQueryService queryService) {
        this.queryService = queryService;
    }

    @GetMapping("/series")
    public ResponseEntity<List<CatalogSeries>> getAllSeries() {
        return ResponseEntity.ok(queryService.getAllSeries());
    }

    @GetMapping("/series/{id}")
    public ResponseEntity<CatalogSeriesResponse> getSeriesDetail(@PathVariable String id) {
        return ResponseEntity.ok(queryService.getSeriesDetail(id));
    }

    @GetMapping("/episodes/{id}")
    public ResponseEntity<CatalogEpisodeResponse> getEpisodeDetail(@PathVariable String id) {
        return ResponseEntity.ok(queryService.getEpisodeDetail(id));
    }

    @GetMapping("/search")
    public ResponseEntity<List<CatalogSearchResult>> searchCatalog(@RequestParam(value = "q", defaultValue = "") String q) {
        return ResponseEntity.ok(queryService.searchCatalog(q));
    }
}
