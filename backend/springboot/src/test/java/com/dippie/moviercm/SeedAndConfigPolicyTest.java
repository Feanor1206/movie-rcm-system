package com.dippie.moviercm;

import com.dippie.moviercm.config.DataInitializer;
import com.dippie.moviercm.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@ActiveProfiles("test")
@TestPropertySource(properties = {
        "app.seed.enabled=false",
        "spring.sql.init.mode=never"
})
public class SeedAndConfigPolicyTest {

    @Autowired(required = false)
    private DataInitializer dataInitializer;

    @Autowired
    private UserRepository userRepository;

    @Test
    @DisplayName("P0 Policy: DataInitializer must NOT be instantiated when app.seed.enabled is false")
    void testDataInitializerBeanNotCreatedWhenSeedDisabled() {
        assertNull(dataInitializer,
                "DataInitializer bean must NOT be loaded into the ApplicationContext when app.seed.enabled=false");
    }

    @Test
    @DisplayName("P0 Policy: Clean isolated test profile must not auto-seed demo accounts")
    void testDemoUsersNotAutoSeededWhenSeedDisabled() {
        // Assert no demo users like 'user1' or 'user50' exist automatically from DataInitializer
        assertFalse(userRepository.existsByUsername("user1"),
                "User 'user1' must NOT exist when seed policy is disabled");
        assertFalse(userRepository.existsByUsername("user50"),
                "User 'user50' must NOT exist when seed policy is disabled");
    }
}
