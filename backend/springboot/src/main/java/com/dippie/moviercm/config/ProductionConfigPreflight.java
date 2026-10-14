package com.dippie.moviercm.config;

import org.springframework.beans.BeansException;
import org.springframework.beans.factory.config.BeanFactoryPostProcessor;
import org.springframework.beans.factory.config.ConfigurableListableBeanFactory;
import org.springframework.context.EnvironmentAware;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;

import java.util.Arrays;

/**
 * Production environment config preflight validator.
 * Ensures mandatory production secrets (APP_JWT_SECRET, SPRING_DATASOURCE_PASSWORD)
 * are provided and resolved before any database connections or application beans are instantiated.
 */
@Configuration
public class ProductionConfigPreflight implements BeanFactoryPostProcessor, EnvironmentAware {

    private Environment environment;

    @Override
    public void setEnvironment(Environment environment) {
        this.environment = environment;
    }

    @Override
    public void postProcessBeanFactory(ConfigurableListableBeanFactory beanFactory) throws BeansException {
        if (environment == null) {
            return;
        }

        boolean isProd = Arrays.asList(environment.getActiveProfiles()).contains("prod");
        if (!isProd) {
            return;
        }

        String jwtSecret = environment.getProperty("app.jwt.secret");
        if (jwtSecret == null || jwtSecret.isBlank() || jwtSecret.contains("${APP_JWT_SECRET}")) {
            throw new IllegalStateException("Production preflight error: Could not resolve placeholder 'APP_JWT_SECRET'");
        }

        String dbPassword = environment.getProperty("spring.datasource.password");
        if (dbPassword == null || dbPassword.isBlank() || dbPassword.contains("${SPRING_DATASOURCE_PASSWORD}")) {
            throw new IllegalStateException("Production preflight error: Could not resolve placeholder 'SPRING_DATASOURCE_PASSWORD'");
        }
    }
}
