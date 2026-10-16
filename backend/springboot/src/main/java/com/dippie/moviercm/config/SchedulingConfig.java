package com.dippie.moviercm.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Enables Spring task scheduling for background outbox workers and maintenance tasks (G1).
 */
@Configuration
@EnableScheduling
public class SchedulingConfig {
}
