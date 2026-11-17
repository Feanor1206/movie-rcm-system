package com.dippie.moviercm;

import com.dippie.moviercm.security.JwtUtils;
import com.dippie.moviercm.service.catalog.CatalogValidator;
import com.dippie.moviercm.dto.catalog.CatalogValidationError;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.io.Decoders;
import io.jsonwebtoken.security.Keys;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import javax.crypto.SecretKey;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Date;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@ActiveProfiles("test")
public class CrossCompatibilityTest {

    @Autowired
    private JwtUtils jwtUtils;

    @Autowired
    private CatalogValidator catalogValidator;

    @Autowired
    private ObjectMapper objectMapper;

    @Value("${app.jwt.secret}")
    private String jwtSecret;

    @Test
    @DisplayName("Cross-compatibility: Validate Python-generated JWT token in Spring Boot JwtUtils")
    void testValidatePythonGeneratedJwtToken() {
        SecretKey key = Keys.hmacShaKeyFor(Decoders.BASE64.decode(jwtSecret));
        String pythonSimulatedToken = Jwts.builder()
                .subject("python_main_tester")
                .issuedAt(new Date(System.currentTimeMillis()))
                .expiration(new Date(System.currentTimeMillis() + 86400000L))
                .signWith(key, Jwts.SIG.HS256)
                .compact();

        assertTrue(jwtUtils.validateJwtToken(pythonSimulatedToken));
        assertEquals("python_main_tester", jwtUtils.getUserNameFromJwtToken(pythonSimulatedToken));
    }

    @Test
    @DisplayName("Cross-compatibility: Reject Playback Grant as general auth token")
    void testRejectPlaybackGrantAsGeneralAuthToken() {
        String playbackGrant = jwtUtils.generatePlaybackGrant("ast-test", "user1", "ROLE_USER", 60000L);
        assertFalse(jwtUtils.validateJwtToken(playbackGrant));
        assertTrue(jwtUtils.validatePlaybackGrant(playbackGrant, "ast-test"));
    }

    @Test
    @DisplayName("Cross-compatibility: Validate rehearsal catalog JSON using Java CatalogValidator")
    void testValidateRehearsalCatalogJson() throws Exception {
        Path catalogPath = Paths.get("../../docs/fixtures/rehearsal_catalog.json");
        if (!Files.exists(catalogPath)) {
            catalogPath = Paths.get("docs/fixtures/rehearsal_catalog.json");
        }
        assertTrue(Files.exists(catalogPath), "rehearsal_catalog.json must exist at " + catalogPath.toAbsolutePath());

        JsonNode catalogNode = objectMapper.readTree(catalogPath.toFile());
        List<CatalogValidationError> errors = catalogValidator.validate(catalogNode);
        assertTrue(errors.isEmpty(), "rehearsal_catalog.json must have 0 validation errors: " + errors);
    }
}
