package com.dippie.moviercm;

import com.dippie.moviercm.config.DataInitializer;
import com.dippie.moviercm.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.core.env.Environment;
import org.springframework.test.context.ActiveProfiles;

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

    @Test
    @DisplayName("P0 Policy: Prod profile fails startup when mandatory secrets are absent")
    void testProdProfileFailsWhenRequiredSecretsMissing() {
        ApplicationContextRunner contextRunner = new ApplicationContextRunner()
                .withUserConfiguration(MovieRcmApplication.class)
                .withPropertyValues("spring.profiles.active=prod");

        contextRunner.run(context -> {
            // Must fail context creation because ${SPRING_DATASOURCE_PASSWORD} and ${APP_JWT_SECRET} cannot be resolved
            assertThat(context).hasFailed();
            Throwable root = context.getStartupFailure();
            while (root.getCause() != null) {
                root = root.getCause();
            }
            assertThat(root).isInstanceOf(IllegalArgumentException.class);
            assertThat(root.getMessage()).contains("Could not resolve placeholder");
        });
    }
}
