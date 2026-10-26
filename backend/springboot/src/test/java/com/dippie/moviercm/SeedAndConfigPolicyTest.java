package com.dippie.moviercm;

import com.dippie.moviercm.config.DataInitializer;
import com.dippie.moviercm.repository.FavoriteItemRepository;
import com.dippie.moviercm.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.Environment;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.MutablePropertySources;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.env.SystemEnvironmentPropertySource;
import org.springframework.core.io.PathResource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import org.springframework.test.context.ActiveProfiles;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@ActiveProfiles("test")
public class SeedAndConfigPolicyTest {

    @Autowired(required = false)
    private DataInitializer dataInitializer;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private Environment environment;

    private void executeSqlFile(String jdbcUrl, String relativePath) {
        Path path = Paths.get(relativePath);
        if (!Files.exists(path)) {
            path = Paths.get("../../" + relativePath);
        }
        assertTrue(Files.exists(path), "Target SQL script must exist on filesystem: " + relativePath);
        try (Connection conn = DriverManager.getConnection(jdbcUrl, "sa", "valid_prod_fixture_password")) {
            ScriptUtils.executeSqlScript(conn, new PathResource(path));
        } catch (SQLException e) {
            throw new RuntimeException("Failed executing SQL script " + path + ": " + e.getMessage(), e);
        }
    }

    @Test
    @DisplayName("P0 Policy: DataInitializer must NOT be instantiated by default in test profile")
    void testDataInitializerBeanNotCreatedWhenSeedDisabled() {
        assertNull(dataInitializer,
                "DataInitializer bean must NOT be loaded into the ApplicationContext when app.seed.enabled=false");
    }

    @Test
    @DisplayName("P0 Policy: Clean isolated test profile must not auto-seed demo accounts")
    void testDemoUsersNotAutoSeededWhenSeedDisabled() {
        assertFalse(userRepository.existsByUsername("user1"),
                "User 'user1' must NOT exist when seed policy is disabled");
        assertFalse(userRepository.existsByUsername("user50"),
                "User 'user50' must NOT exist when seed policy is disabled");
    }

    @Test
    @DisplayName("P0 Policy: Test profile defaults app.seed.enabled to false and sql.init.mode to never")
    void testTestProfileDefaultProperties() {
        assertEquals("false", environment.getProperty("app.seed.enabled"),
                "app.seed.enabled must default to false in test profile");
        assertEquals("never", environment.getProperty("spring.sql.init.mode"),
                "spring.sql.init.mode must default to never in test profile");
    }

    private ConfigurableEnvironment createIsolatedProdEnvironment(Map<String, Object> customProperties) {
        StandardEnvironment env = new StandardEnvironment() {
            @Override
            protected void customizePropertySources(MutablePropertySources propertySources) {
                // Remove spring.profiles.active from system properties to isolate from CI -D arguments
                Properties sysProps = new Properties();
                sysProps.putAll(System.getProperties());
                sysProps.remove("spring.profiles.active");
                propertySources.addLast(new MapPropertySource(
                        SYSTEM_PROPERTIES_PROPERTY_SOURCE_NAME,
                        (Map) sysProps
                ));

                // Remove SPRING_PROFILES_ACTIVE from system environment
                Map<String, Object> sysEnv = new HashMap<>(System.getenv());
                sysEnv.remove("SPRING_PROFILES_ACTIVE");
                sysEnv.remove("spring.profiles.active");
                propertySources.addLast(new SystemEnvironmentPropertySource(
                        SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME,
                        sysEnv
                ));
            }
        };

        // Explicitly set active profiles to ONLY "prod"
        env.setActiveProfiles("prod");

        Map<String, Object> props = new HashMap<>();
        props.put("spring.profiles.active", "prod");
        if (customProperties != null) {
            props.putAll(customProperties);
        }

        env.getPropertySources().addFirst(new MapPropertySource("isolatedProdCustomProperties", props));

        return env;
    }

    private SpringApplicationBuilder createIsolatedProdBuilder(ConfigurableEnvironment env) {
        return new SpringApplicationBuilder(MovieRcmApplication.class)
                .environment(env)
                .profiles("prod")
                .web(WebApplicationType.NONE);
    }

    @Test
    @DisplayName("Positive Control: Prod profile loads actual YAML, starts and validates when valid secrets and schema exist")
    void testProdProfileStartsSuccessfullyWithValidSecretsAndSchema() {
        String dbName = "prod_positive_" + UUID.randomUUID();
        String jdbcUrl = "jdbc:h2:mem:" + dbName + ";DB_CLOSE_DELAY=-1;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DEFAULT_NULL_ORDERING=HIGH";

        executeSqlFile(jdbcUrl, "../../database/schema/01_init.sql");

        Map<String, Object> props = new HashMap<>();
        props.put("SPRING_DATASOURCE_URL", jdbcUrl);
        props.put("SPRING_DATASOURCE_DRIVER_CLASS_NAME", "org.h2.Driver");
        props.put("SPRING_DATASOURCE_USERNAME", "sa");
        props.put("spring.jpa.properties.hibernate.dialect", "org.hibernate.dialect.H2Dialect");
        props.put("SPRING_DATASOURCE_PASSWORD", "valid_prod_fixture_password");
        props.put("APP_JWT_SECRET", "404E635266556A586E3272357538782F413F4428472B4B6250645367566B5970");

        ConfigurableEnvironment env = createIsolatedProdEnvironment(props);
        ConfigurableApplicationContext ctx = null;
        try {
            ctx = createIsolatedProdBuilder(env).run("--spring.profiles.active=prod");

            assertNotNull(ctx);
            assertTrue(ctx.isRunning());
            assertArrayEquals(new String[]{"prod"}, ctx.getEnvironment().getActiveProfiles(),
                    "Active profiles must contain exactly and only 'prod'");
            assertEquals("false", ctx.getEnvironment().getProperty("app.seed.enabled"),
                    "Production policy must have app.seed.enabled=false");
            assertEquals("never", ctx.getEnvironment().getProperty("spring.sql.init.mode"),
                    "Production policy must have spring.sql.init.mode=never");
            assertEquals("validate", ctx.getEnvironment().getProperty("spring.jpa.hibernate.ddl-auto"),
                    "Production policy must enforce ddl-auto=validate");
            assertNotNull(ctx.getBean(UserRepository.class));
            assertNotNull(ctx.getBean(FavoriteItemRepository.class));
        } finally {
            if (ctx != null) {
                ctx.close();
            }
        }
    }

    @Test
    @DisplayName("Negative Control: Prod profile fails with specific placeholder error when APP_JWT_SECRET is missing")
    void testProdProfileFailsWhenJwtSecretMissing() {
        String dbName = "prod_no_jwt_" + UUID.randomUUID();
        String jdbcUrl = "jdbc:h2:mem:" + dbName + ";DB_CLOSE_DELAY=-1;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE";

        executeSqlFile(jdbcUrl, "../../database/schema/01_init.sql");

        Map<String, Object> props = new HashMap<>();
        props.put("SPRING_DATASOURCE_URL", jdbcUrl);
        props.put("SPRING_DATASOURCE_DRIVER_CLASS_NAME", "org.h2.Driver");
        props.put("SPRING_DATASOURCE_USERNAME", "sa");
        props.put("spring.jpa.properties.hibernate.dialect", "org.hibernate.dialect.H2Dialect");
        props.put("SPRING_DATASOURCE_PASSWORD", "valid_prod_fixture_password");
        // Intentionally omitting APP_JWT_SECRET

        ConfigurableEnvironment env = createIsolatedProdEnvironment(props);

        Exception exception = assertThrows(Exception.class, () -> {
            createIsolatedProdBuilder(env).run("--spring.profiles.active=prod");
        });

        // Verify the failure chain contains the unresolvable placeholder error
        String fullError = getFullStackTrace(exception);
        assertThat(fullError).contains("Could not resolve placeholder 'APP_JWT_SECRET'");
    }

    @Test
    @DisplayName("Negative Control: Prod profile fails with specific placeholder error when SPRING_DATASOURCE_PASSWORD is missing")
    void testProdProfileFailsWhenDatasourcePasswordMissing() {
        String dbName = "prod_no_pw_" + UUID.randomUUID();
        String jdbcUrl = "jdbc:h2:mem:" + dbName + ";DB_CLOSE_DELAY=-1;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE";

        executeSqlFile(jdbcUrl, "../../database/schema/01_init.sql");

        Map<String, Object> props = new HashMap<>();
        props.put("SPRING_DATASOURCE_URL", jdbcUrl);
        props.put("SPRING_DATASOURCE_DRIVER_CLASS_NAME", "org.h2.Driver");
        props.put("SPRING_DATASOURCE_USERNAME", "sa");
        props.put("spring.jpa.properties.hibernate.dialect", "org.hibernate.dialect.H2Dialect");
        props.put("APP_JWT_SECRET", "404E635266556A586E3272357538782F413F4428472B4B6250645367566B5970");
        // Intentionally omitting SPRING_DATASOURCE_PASSWORD

        ConfigurableEnvironment env = createIsolatedProdEnvironment(props);

        Exception exception = assertThrows(Exception.class, () -> {
            createIsolatedProdBuilder(env).run("--spring.profiles.active=prod");
        });

        // Verify the failure chain contains the unresolvable placeholder error
        String fullError = getFullStackTrace(exception);
        assertThat(fullError).contains("Could not resolve placeholder 'SPRING_DATASOURCE_PASSWORD'");
    }

    @Test
    @DisplayName("C1 Canonical Bootstrap: 01_init.sql initializes all 5 tables including favorite_items and passes Hibernate validate")
    void testCanonicalInitScriptPassesHibernateValidate() throws Exception {
        String dbName = "bootstrap_canon_" + UUID.randomUUID();
        String jdbcUrl = "jdbc:h2:mem:" + dbName + ";DB_CLOSE_DELAY=-1;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DEFAULT_NULL_ORDERING=HIGH";

        executeSqlFile(jdbcUrl, "../../database/schema/01_init.sql");

        // Verify all 5 tables exist directly via JDBC queries
        try (Connection conn = DriverManager.getConnection(jdbcUrl, "sa", "valid_prod_fixture_password")) {
            try (Statement stmt = conn.createStatement()) {
                ResultSet rs = stmt.executeQuery("SELECT count(*) FROM favorite_items");
                assertTrue(rs.next());
                assertEquals(0, rs.getInt(1), "favorite_items table must exist and return 0 count");

                rs = stmt.executeQuery("SELECT count(*) FROM users");
                assertTrue(rs.next());
                assertEquals(0, rs.getInt(1));

                rs = stmt.executeQuery("SELECT count(*) FROM movies");
                assertTrue(rs.next());
                assertEquals(0, rs.getInt(1));

                rs = stmt.executeQuery("SELECT count(*) FROM watchlist_items");
                assertTrue(rs.next());
                assertEquals(0, rs.getInt(1));

                rs = stmt.executeQuery("SELECT count(*) FROM movie_ratings");
                assertTrue(rs.next());
                assertEquals(0, rs.getInt(1));
            }
        }

        // Verify Hibernate ddl-auto=validate succeeds without schema mismatch errors
        Map<String, Object> props = new HashMap<>();
        props.put("SPRING_DATASOURCE_URL", jdbcUrl);
        props.put("SPRING_DATASOURCE_DRIVER_CLASS_NAME", "org.h2.Driver");
        props.put("SPRING_DATASOURCE_USERNAME", "sa");
        props.put("spring.jpa.properties.hibernate.dialect", "org.hibernate.dialect.H2Dialect");
        props.put("SPRING_DATASOURCE_PASSWORD", "valid_prod_fixture_password");
        props.put("APP_JWT_SECRET", "404E635266556A586E3272357538782F413F4428472B4B6250645367566B5970");
        props.put("spring.jpa.hibernate.ddl-auto", "validate");

        ConfigurableEnvironment env = createIsolatedProdEnvironment(props);
        ConfigurableApplicationContext ctx = null;
        try {
            ctx = createIsolatedProdBuilder(env).run("--spring.profiles.active=prod");

            assertNotNull(ctx);
            assertTrue(ctx.isRunning());
            assertArrayEquals(new String[]{"prod"}, ctx.getEnvironment().getActiveProfiles(),
                    "Active profiles must contain exactly and only 'prod'");
            assertEquals("validate", ctx.getEnvironment().getProperty("spring.jpa.hibernate.ddl-auto"));
            assertNotNull(ctx.getBean(FavoriteItemRepository.class));
        } finally {
            if (ctx != null) {
                ctx.close();
            }
        }
    }

    @Test
    @DisplayName("C1 Additive Migration: 02_add_favorite_items.sql safely upgrades legacy 4-table schema preserving user data")
    void testAdditiveMigrationPreservesDataAndPassesValidate() throws Exception {
        String dbName = "migration_test_" + UUID.randomUUID();
        String jdbcUrl = "jdbc:h2:mem:" + dbName + ";DB_CLOSE_DELAY=-1;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DEFAULT_NULL_ORDERING=HIGH";

        // 1. Create legacy 4-table schema (without favorite_items) and insert sample data
        try (Connection conn = DriverManager.getConnection(jdbcUrl, "sa", "valid_prod_fixture_password")) {
            try (Statement stmt = conn.createStatement()) {
                stmt.execute("CREATE TABLE users (id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, username VARCHAR(50) NOT NULL UNIQUE, email VARCHAR(100) NOT NULL UNIQUE, password VARCHAR(255) NOT NULL, full_name VARCHAR(100), role VARCHAR(20) DEFAULT 'ROLE_USER', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);");
                stmt.execute("CREATE TABLE movies (id VARCHAR(100) PRIMARY KEY, title VARCHAR(255) NOT NULL, release_year INT NOT NULL, rating DOUBLE PRECISION NOT NULL, runtime VARCHAR(20), genres TEXT, description TEXT, poster VARCHAR(500), backdrop VARCHAR(500), video_url VARCHAR(500), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);");
                stmt.execute("CREATE TABLE watchlist_items (id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, user_id BIGINT NOT NULL, movie_id VARCHAR(100) NOT NULL, movie_title VARCHAR(255) NOT NULL, poster_url VARCHAR(500), added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, CONSTRAINT fk_watchlist_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE, CONSTRAINT uq_user_movie_watchlist UNIQUE (user_id, movie_id));");
                stmt.execute("CREATE TABLE movie_ratings (id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, user_id BIGINT NOT NULL, movie_id VARCHAR(100) NOT NULL, rating INT NOT NULL CHECK (rating >= 1 AND rating <= 10), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, CONSTRAINT fk_rating_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE, CONSTRAINT uq_user_movie_rating UNIQUE (user_id, movie_id));");

                // Insert existing data
                stmt.execute("INSERT INTO users (username, email, password, full_name) VALUES ('legacy_user', 'legacy@example.com', 'hashed_pw', 'Legacy User');");
                stmt.execute("INSERT INTO movies (id, title, release_year, rating) VALUES ('movie_1', 'Legacy Movie', 2020, 8.5);");
                stmt.execute("INSERT INTO watchlist_items (user_id, movie_id, movie_title) VALUES (1, 'movie_1', 'Legacy Movie');");
                stmt.execute("INSERT INTO movie_ratings (user_id, movie_id, rating) VALUES (1, 'movie_1', 9);");
            }
        }

        // 2. Assert favorite_items and media_assets do NOT exist prior to migration
        try (Connection conn = DriverManager.getConnection(jdbcUrl, "sa", "valid_prod_fixture_password")) {
            try (Statement stmt = conn.createStatement()) {
                assertThrows(SQLException.class, () -> stmt.executeQuery("SELECT count(*) FROM favorite_items"));
                assertThrows(SQLException.class, () -> stmt.executeQuery("SELECT count(*) FROM media_assets"));
            }
        }

        // 3. Execute additive migrations: 02_add_favorite_items.sql, 03_add_media_assets.sql, 04_add_catalog_tables.sql
        executeSqlFile(jdbcUrl, "../../database/migrations/02_add_favorite_items.sql");
        executeSqlFile(jdbcUrl, "../../database/migrations/03_add_media_assets.sql");
        executeSqlFile(jdbcUrl, "../../database/migrations/04_add_catalog_tables.sql");
        executeSqlFile(jdbcUrl, "../../database/migrations/05_add_watch_progress.sql");

        // 4. Assert favorite_items & media_assets exist and prior data is 100% intact
        try (Connection conn = DriverManager.getConnection(jdbcUrl, "sa", "valid_prod_fixture_password")) {
            try (Statement stmt = conn.createStatement()) {
                ResultSet rs = stmt.executeQuery("SELECT count(*) FROM favorite_items");
                assertTrue(rs.next());
                assertEquals(0, rs.getInt(1));

                rs = stmt.executeQuery("SELECT count(*) FROM media_assets");
                assertTrue(rs.next());
                assertEquals(0, rs.getInt(1));

                // Verify existing data untouched
                rs = stmt.executeQuery("SELECT username FROM users WHERE username = 'legacy_user'");
                assertTrue(rs.next());
                assertEquals("legacy_user", rs.getString(1));

                rs = stmt.executeQuery("SELECT count(*) FROM watchlist_items");
                assertTrue(rs.next());
                assertEquals(1, rs.getInt(1));

                rs = stmt.executeQuery("SELECT rating FROM movie_ratings WHERE user_id = 1");
                assertTrue(rs.next());
                assertEquals(9, rs.getInt(1));
            }
        }

        // 5. Assert Hibernate ddl-auto=validate succeeds on the upgraded database
        Map<String, Object> props = new HashMap<>();
        props.put("SPRING_DATASOURCE_URL", jdbcUrl);
        props.put("SPRING_DATASOURCE_DRIVER_CLASS_NAME", "org.h2.Driver");
        props.put("SPRING_DATASOURCE_USERNAME", "sa");
        props.put("spring.jpa.properties.hibernate.dialect", "org.hibernate.dialect.H2Dialect");
        props.put("SPRING_DATASOURCE_PASSWORD", "valid_prod_fixture_password");
        props.put("APP_JWT_SECRET", "404E635266556A586E3272357538782F413F4428472B4B6250645367566B5970");
        props.put("spring.jpa.hibernate.ddl-auto", "validate");

        ConfigurableEnvironment env = createIsolatedProdEnvironment(props);
        ConfigurableApplicationContext ctx = null;
        try {
            ctx = createIsolatedProdBuilder(env).run("--spring.profiles.active=prod");

            assertNotNull(ctx);
            assertTrue(ctx.isRunning());
            assertArrayEquals(new String[]{"prod"}, ctx.getEnvironment().getActiveProfiles(),
                    "Active profiles must contain exactly and only 'prod'");
            assertEquals("validate", ctx.getEnvironment().getProperty("spring.jpa.hibernate.ddl-auto"));
            assertNotNull(ctx.getBean(FavoriteItemRepository.class));
            assertNotNull(ctx.getBean(com.dippie.moviercm.repository.MediaAssetRepository.class));

        } finally {
            if (ctx != null) {
                ctx.close();
            }
        }
    }

    private String getFullStackTrace(Throwable t) {
        java.io.StringWriter sw = new java.io.StringWriter();
        t.printStackTrace(new java.io.PrintWriter(sw));
        return sw.toString();
    }
}
