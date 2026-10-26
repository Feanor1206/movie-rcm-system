package com.dippie.moviercm.config;

import com.dippie.moviercm.security.AuthEntryPointJwt;
import com.dippie.moviercm.security.AuthAdmissionFilter;
import com.dippie.moviercm.security.JwtAuthenticationFilter;
import com.dippie.moviercm.security.UserDetailsServiceImpl;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.core.env.Environment;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.dao.DaoAuthenticationProvider;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.util.matcher.AntPathRequestMatcher;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.Arrays;
import java.util.List;
import java.net.URI;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {

    private final UserDetailsServiceImpl userDetailsService;
    private final AuthEntryPointJwt unauthorizedHandler;
    private final JwtAuthenticationFilter jwtAuthenticationFilter;
    private final AuthAdmissionFilter authAdmissionFilter;
    private final Environment environment;

    @Value("${app.cors.allowed-origins:http://localhost:3000,http://127.0.0.1:3000}")
    private String allowedOrigins;

    public SecurityConfig(UserDetailsServiceImpl userDetailsService,
                          AuthEntryPointJwt unauthorizedHandler,
                          JwtAuthenticationFilter jwtAuthenticationFilter,
                          AuthAdmissionFilter authAdmissionFilter,
                          Environment environment) {
        this.userDetailsService = userDetailsService;
        this.unauthorizedHandler = unauthorizedHandler;
        this.jwtAuthenticationFilter = jwtAuthenticationFilter;
        this.authAdmissionFilter = authAdmissionFilter;
        this.environment = environment;
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public DaoAuthenticationProvider authenticationProvider() {
        DaoAuthenticationProvider authProvider = new DaoAuthenticationProvider();
        authProvider.setUserDetailsService(userDetailsService);
        authProvider.setPasswordEncoder(passwordEncoder());
        return authProvider;
    }

    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration authConfig) throws Exception {
        return authConfig.getAuthenticationManager();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOrigins(parseAllowedOrigins(allowedOrigins));
        configuration.setAllowedMethods(Arrays.asList("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"));
        configuration.setAllowedHeaders(Arrays.asList("Authorization", "Content-Type", "X-Auth-Token", "Accept", "Origin", "X-Requested-With", "Range", "If-Range"));
        configuration.setExposedHeaders(List.of("Authorization", "X-Auth-Token", "Content-Range", "Accept-Ranges", "Content-Length", "Content-Type"));
        configuration.setAllowCredentials(true);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }

    static List<String> parseAllowedOrigins(String configuredOrigins) {
        if (configuredOrigins == null || configuredOrigins.isBlank()) {
            throw new IllegalStateException("app.cors.allowed-origins must contain at least one explicit origin.");
        }
        List<String> origins = Arrays.stream(configuredOrigins.split(","))
                .map(String::trim)
                .filter(origin -> !origin.isEmpty())
                .toList();
        if (origins.isEmpty()) {
            throw new IllegalStateException("app.cors.allowed-origins must contain at least one explicit origin.");
        }
        for (String origin : origins) {
            if (origin.contains("*")) {
                throw new IllegalStateException("Wildcard origins are not allowed when credentialed CORS is enabled.");
            }
            try {
                URI uri = URI.create(origin);
                String scheme = uri.getScheme();
                if (uri.getHost() == null || uri.getUserInfo() != null
                        || !("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme))
                        || (uri.getRawPath() != null && !uri.getRawPath().isEmpty())
                        || uri.getQuery() != null || uri.getFragment() != null) {
                    throw new IllegalStateException("Invalid CORS origin: " + origin);
                }
            } catch (IllegalArgumentException invalidOrigin) {
                throw new IllegalStateException("Invalid CORS origin: " + origin, invalidOrigin);
            }
        }
        return List.copyOf(origins);
    }

    static boolean isH2ConsoleExposureEnabled(Environment environment) {
        List<String> profiles = Arrays.asList(environment.getActiveProfiles());
        boolean developmentProfile = profiles.stream()
                .anyMatch(profile -> "dev".equals(profile) || "test".equals(profile));
        boolean productionProfile = profiles.contains("prod");
        return developmentProfile && !productionProfile
                && environment.getProperty("app.security.h2-console.enabled", Boolean.class, false)
                && environment.getProperty("spring.h2.console.enabled", Boolean.class, false);
    }

    @Bean
    @Order(Ordered.HIGHEST_PRECEDENCE)
    public SecurityFilterChain h2ConsoleFilterChain(HttpSecurity http) throws Exception {
        boolean consoleEnabled = isH2ConsoleExposureEnabled(environment);
        http.securityMatcher(new AntPathRequestMatcher("/h2-console/**"))
                .csrf(csrf -> csrf.disable())
                .authorizeHttpRequests(auth -> {
                    if (consoleEnabled) {
                        auth.anyRequest().permitAll();
                    } else {
                        auth.anyRequest().denyAll();
                    }
                });
        if (consoleEnabled) {
            http.headers(headers -> headers.frameOptions(frame -> frame.sameOrigin()));
        }
        return http.build();
    }

    @Bean
    public FilterRegistrationBean<AuthAdmissionFilter> authAdmissionFilterRegistration() {
        FilterRegistrationBean<AuthAdmissionFilter> registration = new FilterRegistrationBean<>(authAdmissionFilter);
        registration.setEnabled(false);
        return registration;
    }

    @Bean
    @Order(Ordered.LOWEST_PRECEDENCE)
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .csrf(csrf -> csrf.disable())
            .exceptionHandling(exception -> exception.authenticationEntryPoint(unauthorizedHandler))
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                .requestMatchers("/api/auth/**").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/movies/**").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/catalog/**").permitAll()
                .requestMatchers("/api/admin/catalog/**").hasRole("ADMIN")
                .requestMatchers(HttpMethod.GET, "/api/health/**").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/media/**").permitAll()
                .requestMatchers(HttpMethod.HEAD, "/api/media/**").permitAll()
                .requestMatchers("/error").permitAll()
                .anyRequest().authenticated()
            );

        http.authenticationProvider(authenticationProvider());
        http.addFilterBefore(authAdmissionFilter, UsernamePasswordAuthenticationFilter.class);
        http.addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }
}
