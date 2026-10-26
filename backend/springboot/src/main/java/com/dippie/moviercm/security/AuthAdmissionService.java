package com.dippie.moviercm.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

@Service
public class AuthAdmissionService {

    enum Endpoint { LOGIN, REGISTER }

    record Admission(boolean allowed, long retryAfterSeconds) {}

    private static final String UNKNOWN_REMOTE = "unknown";

    private final int loginLimit;
    private final long loginWindowMillis;
    private final int registerLimit;
    private final long registerWindowMillis;
    private final int maxTrackedIps;
    private final Map<String, IpWindows> clients = new HashMap<>();

    public AuthAdmissionService(
            @Value("${app.auth.rate-limit.login.max-attempts:30}") int loginLimit,
            @Value("${app.auth.rate-limit.login.window-seconds:60}") long loginWindowSeconds,
            @Value("${app.auth.rate-limit.register.max-attempts:20}") int registerLimit,
            @Value("${app.auth.rate-limit.register.window-seconds:3600}") long registerWindowSeconds,
            @Value("${app.auth.rate-limit.max-tracked-ips:10000}") int maxTrackedIps) {
        if (loginLimit < 1 || registerLimit < 1 || loginWindowSeconds < 1 || registerWindowSeconds < 1 || maxTrackedIps < 1) {
            throw new IllegalArgumentException("Authentication rate limits and tracked IP capacity must be positive.");
        }
        this.loginLimit = loginLimit;
        this.loginWindowMillis = Math.multiplyExact(loginWindowSeconds, 1000L);
        this.registerLimit = registerLimit;
        this.registerWindowMillis = Math.multiplyExact(registerWindowSeconds, 1000L);
        this.maxTrackedIps = maxTrackedIps;
    }

    Admission tryAdmit(String remoteAddress, Endpoint endpoint) {
        return tryAdmit(remoteAddress, endpoint, System.currentTimeMillis());
    }

    synchronized Admission tryAdmit(String remoteAddress, Endpoint endpoint, long nowMillis) {
        removeExpiredClients(nowMillis);
        String clientIp = remoteAddress == null || remoteAddress.isBlank() ? UNKNOWN_REMOTE : remoteAddress;
        IpWindows windows = clients.get(clientIp);
        if (windows == null) {
            if (clients.size() >= maxTrackedIps) {
                return new Admission(false, secondsUntil(earliestClientExpiry(nowMillis), nowMillis));
            }
            windows = new IpWindows();
            clients.put(clientIp, windows);
        }

        Window window = endpoint == Endpoint.LOGIN ? windows.login : windows.register;
        int limit = endpoint == Endpoint.LOGIN ? loginLimit : registerLimit;
        long duration = endpoint == Endpoint.LOGIN ? loginWindowMillis : registerWindowMillis;
        if (window.attempts == 0 || nowMillis >= window.resetAtMillis) {
            window.attempts = 0;
            window.resetAtMillis = nowMillis + duration;
        }
        if (window.attempts >= limit) {
            return new Admission(false, secondsUntil(window.resetAtMillis, nowMillis));
        }

        window.attempts++;
        return new Admission(true, 0);
    }

    synchronized int trackedIpCount() {
        return clients.size();
    }

    private void removeExpiredClients(long nowMillis) {
        Iterator<Map.Entry<String, IpWindows>> iterator = clients.entrySet().iterator();
        while (iterator.hasNext()) {
            IpWindows windows = iterator.next().getValue();
            if (windows.login.isExpired(nowMillis) && windows.register.isExpired(nowMillis)) {
                iterator.remove();
            }
        }
    }

    private long earliestClientExpiry(long nowMillis) {
        long earliest = Long.MAX_VALUE;
        for (IpWindows windows : clients.values()) {
            long expiry = Math.max(windows.login.expiryOrNow(nowMillis), windows.register.expiryOrNow(nowMillis));
            earliest = Math.min(earliest, expiry);
        }
        return earliest == Long.MAX_VALUE ? nowMillis + 1000L : earliest;
    }

    private static long secondsUntil(long deadlineMillis, long nowMillis) {
        return Math.max(1L, (Math.max(0L, deadlineMillis - nowMillis) + 999L) / 1000L);
    }

    private static final class IpWindows {
        private final Window login = new Window();
        private final Window register = new Window();
    }

    private static final class Window {
        private int attempts;
        private long resetAtMillis;

        private boolean isExpired(long nowMillis) {
            return attempts == 0 || nowMillis >= resetAtMillis;
        }

        private long expiryOrNow(long nowMillis) {
            return isExpired(nowMillis) ? nowMillis : resetAtMillis;
        }
    }
}
