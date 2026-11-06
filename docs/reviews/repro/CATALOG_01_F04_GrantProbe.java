import com.dippie.moviercm.security.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import java.util.*;

/** Production JWT/filter with ephemeral signing key and a fixture-only user loader. */
public class CATALOG_01_F04_GrantProbe {
    static class FixtureUsers extends UserDetailsServiceImpl {
        FixtureUsers(){super(null);}
        @Override public UserDetails loadUserByUsername(String username) {
            return org.springframework.security.core.userdetails.User.withUsername(username)
                .password("").authorities("ROLE_ADMIN").build();
        }
    }
    static boolean bearerAuthenticates(JwtAuthenticationFilter filter,String path,String grant) throws Exception {
        SecurityContextHolder.clearContext();
        var request=new MockHttpServletRequest("GET",path);
        request.addHeader("Authorization","Bearer "+grant);
        filter.doFilter(request,new MockHttpServletResponse(),(req,res)->{});
        var auth=SecurityContextHolder.getContext().getAuthentication();
        boolean accepted=auth!=null && auth.isAuthenticated() && auth.getAuthorities().stream()
            .anyMatch(a->a.getAuthority().equals("ROLE_ADMIN"));
        SecurityContextHolder.clearContext();return accepted;
    }
    public static void main(String[] args) throws Exception {
        JwtUtils jwt=new JwtUtils();
        byte[] key=new byte[64];new java.security.SecureRandom().nextBytes(key);
        var field=JwtUtils.class.getDeclaredField("jwtSecret");field.setAccessible(true);
        field.set(jwt,Base64.getEncoder().encodeToString(key));
        String grant=jwt.generatePlaybackGrant("asset-A","fixture-admin","ROLE_ADMIN",300000);
        JwtAuthenticationFilter filter=new JwtAuthenticationFilter(jwt,new FixtureUsers());
        var results=Map.of(
            "bound_grant_valid_for_A",jwt.validatePlaybackGrant(grant,"asset-A"),
            "bound_grant_valid_for_B",jwt.validatePlaybackGrant(grant,"asset-B"),
            "grant_as_bearer_authenticates_admin_endpoint",bearerAuthenticates(filter,"/api/admin/catalog/history",grant),
            "grant_as_bearer_authenticates_other_asset",bearerAuthenticates(filter,"/api/media/stream/asset-B",grant),
            "scope","production filter with mock servlet request and fixture user; no DB/HTTP; signing key/token not output");
        System.out.println(new ObjectMapper().writeValueAsString(results));
    }
}
