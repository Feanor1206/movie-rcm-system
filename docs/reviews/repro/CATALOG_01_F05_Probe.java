package com.dippie.moviercm;

import com.dippie.moviercm.security.JwtAuthenticationFilter;
import com.dippie.moviercm.security.JwtUtils;
import com.dippie.moviercm.security.UserDetailsServiceImpl;
import com.dippie.moviercm.service.catalog.CatalogImportService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.User;

import java.io.File;
import java.nio.file.Path;
import java.security.SecureRandom;
import java.util.*;

/**
 * F05 Rehearsal Probe: Comprehensive verification of:
 * 1. Playback grant security matrix (R1, R2).
 * 2. Golden vector canonical hashing (R3).
 */
public class CATALOG_01_F05_Probe {

    static class FixtureUsers extends UserDetailsServiceImpl {
        private final boolean userEnabled;
        FixtureUsers(boolean userEnabled) {
            super(null);
            this.userEnabled = userEnabled;
        }

        @Override
        public UserDetails loadUserByUsername(String username) {
            if ("nonexistent".equals(username)) {
                throw new RuntimeException("User not found");
            }
            return User.withUsername(username)
                    .password("")
                    .disabled(!userEnabled)
                    .authorities("ROLE_ADMIN")
                    .build();
        }
    }

    static boolean executeRequest(JwtAuthenticationFilter filter, String method, String uri, String queryParamGrant, String bearerToken) throws Exception {
        SecurityContextHolder.clearContext();
        MockHttpServletRequest request = new MockHttpServletRequest(method, uri);
        if (queryParamGrant != null) {
            request.setParameter("grant", queryParamGrant);
        }
        if (bearerToken != null) {
            request.addHeader("Authorization", "Bearer " + bearerToken);
        }
        filter.doFilter(request, new MockHttpServletResponse(), (req, res) -> {});
        var auth = SecurityContextHolder.getContext().getAuthentication();
        boolean authenticated = auth != null && auth.isAuthenticated() &&
                auth.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));
        SecurityContextHolder.clearContext();
        return authenticated;
    }

    public static void main(String[] args) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        Map<String, Object> output = new LinkedHashMap<>();

        // -------------------------------------------------------------
        // 1. Playback Grant Security Matrix
        // -------------------------------------------------------------
        JwtUtils jwt = new JwtUtils();
        byte[] key = new byte[64];
        new SecureRandom().nextBytes(key);
        var field = JwtUtils.class.getDeclaredField("jwtSecret");
        field.setAccessible(true);
        field.set(jwt, Base64.getEncoder().encodeToString(key));

        String validGrantA = jwt.generatePlaybackGrant("asset-A", "admin", "ROLE_ADMIN", 300000);
        String expiredGrantA = jwt.generatePlaybackGrant("asset-A", "admin", "ROLE_ADMIN", -10000);
        String disabledUserGrant = jwt.generatePlaybackGrant("asset-A", "disabled_user", "ROLE_ADMIN", 300000);

        JwtAuthenticationFilter activeFilter = new JwtAuthenticationFilter(jwt, new FixtureUsers(true));
        JwtAuthenticationFilter disabledUserFilter = new JwtAuthenticationFilter(jwt, new FixtureUsers(false));

        Map<String, Object> grantMatrix = new LinkedHashMap<>();
        // Scope & target binding
        grantMatrix.put("bound_grant_valid_for_A", jwt.validatePlaybackGrant(validGrantA, "asset-A"));
        grantMatrix.put("bound_grant_valid_for_B", jwt.validatePlaybackGrant(validGrantA, "asset-B"));
        // Expired grant rejected
        grantMatrix.put("expired_grant_rejected", !jwt.validatePlaybackGrant(expiredGrantA, "asset-A"));
        // URL query parameter ?grant= on streaming endpoint
        grantMatrix.put("stream_A_with_query_param_authenticated", executeRequest(activeFilter, "GET", "/api/media/stream/asset-A", validGrantA, null));
        grantMatrix.put("stream_A_with_head_method_authenticated", executeRequest(activeFilter, "HEAD", "/api/media/stream/asset-A", validGrantA, null));
        grantMatrix.put("stream_A_with_post_method_rejected", !executeRequest(activeFilter, "POST", "/api/media/stream/asset-A", validGrantA, null));
        grantMatrix.put("stream_B_with_grant_A_query_param_rejected", !executeRequest(activeFilter, "GET", "/api/media/stream/asset-B", validGrantA, null));
        // Bearer header rejection
        grantMatrix.put("grant_as_bearer_authenticates_admin_endpoint", executeRequest(activeFilter, "GET", "/api/admin/catalog/history", null, validGrantA));
        grantMatrix.put("grant_as_bearer_authenticates_other_asset", executeRequest(activeFilter, "GET", "/api/media/stream/asset-B", null, validGrantA));
        grantMatrix.put("grant_as_bearer_authenticates_same_asset", executeRequest(activeFilter, "GET", "/api/media/stream/asset-A", null, validGrantA));
        // Disabled user account rejection
        grantMatrix.put("disabled_user_grant_rejected", !executeRequest(disabledUserFilter, "GET", "/api/media/stream/asset-A", disabledUserGrant, null));

        output.put("grant_security_matrix", grantMatrix);

        // -------------------------------------------------------------
        // 2. Golden Vector Canonical Hashes
        // -------------------------------------------------------------
        if (args.length > 0) {
            String testVectorsFilePath = args[0];
            var vectorsNode = mapper.readTree(new File(testVectorsFilePath));
            Map<String, String> javaHashes = new LinkedHashMap<>();
            Iterator<Map.Entry<String, com.fasterxml.jackson.databind.JsonNode>> fields = vectorsNode.fields();
            while (fields.hasNext()) {
                var entry = fields.next();
                String vectorName = entry.getKey();
                String jsonContent = mapper.writeValueAsString(entry.getValue());
                String hash = CatalogImportService.computeSha256(jsonContent);
                javaHashes.put(vectorName, hash);
            }
            output.put("golden_vector_hashes", javaHashes);
        }

        System.out.println(mapper.writeValueAsString(output));
    }
}
