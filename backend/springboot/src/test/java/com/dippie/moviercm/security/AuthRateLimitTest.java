package com.dippie.moviercm.security;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.mock.web.MockFilterChain;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AuthRateLimitTest {

    @Test
    void loginAndRegistrationUseSeparateConfigurableWindows() {
        AuthAdmissionService service = new AuthAdmissionService(2, 10, 1, 30, 100);

        assertTrue(service.tryAdmit("203.0.113.1", AuthAdmissionService.Endpoint.LOGIN, 1_000).allowed());
        assertTrue(service.tryAdmit("203.0.113.1", AuthAdmissionService.Endpoint.LOGIN, 2_000).allowed());
        AuthAdmissionService.Admission blockedLogin = service.tryAdmit("203.0.113.1", AuthAdmissionService.Endpoint.LOGIN, 3_000);
        assertFalse(blockedLogin.allowed());
        assertEquals(8, blockedLogin.retryAfterSeconds());

        assertTrue(service.tryAdmit("203.0.113.1", AuthAdmissionService.Endpoint.REGISTER, 3_000).allowed());
        AuthAdmissionService.Admission blockedRegister = service.tryAdmit("203.0.113.1", AuthAdmissionService.Endpoint.REGISTER, 4_000);
        assertFalse(blockedRegister.allowed());
        assertEquals(29, blockedRegister.retryAfterSeconds());
        assertTrue(service.tryAdmit("203.0.113.2", AuthAdmissionService.Endpoint.LOGIN, 4_000).allowed());
    }

    @Test
    void expiredIpEntriesAreRemovedBeforeTheTrackedAddressLimitIsApplied() {
        AuthAdmissionService service = new AuthAdmissionService(1, 5, 1, 20, 1);
        assertTrue(service.tryAdmit("203.0.113.10", AuthAdmissionService.Endpoint.LOGIN, 1_000).allowed());

        AuthAdmissionService.Admission full = service.tryAdmit("203.0.113.11", AuthAdmissionService.Endpoint.REGISTER, 2_000);
        assertFalse(full.allowed());
        assertEquals(4, full.retryAfterSeconds());
        assertEquals(1, service.trackedIpCount());

        assertTrue(service.tryAdmit("203.0.113.11", AuthAdmissionService.Endpoint.REGISTER, 6_000).allowed());
        assertEquals(1, service.trackedIpCount());
    }

    @Test
    void filterKeysByRemoteAddressAndReturnsCredentialFree429() throws Exception {
        AuthAdmissionFilter filter = new AuthAdmissionFilter(new AuthAdmissionService(1, 60, 1, 60, 10));

        MockHttpServletRequest firstRequest = loginRequest("10.0.0.9", "198.51.100.1", "first-secret");
        MockHttpServletResponse firstResponse = new MockHttpServletResponse();
        MockFilterChain firstChain = new MockFilterChain();
        filter.doFilter(firstRequest, firstResponse, firstChain);
        assertEquals(200, firstResponse.getStatus());
        assertTrue(firstChain.getRequest() != null);

        MockHttpServletRequest secondRequest = loginRequest("10.0.0.9", "198.51.100.2", "second-secret");
        MockHttpServletResponse secondResponse = new MockHttpServletResponse();
        MockFilterChain secondChain = new MockFilterChain();
        filter.doFilter(secondRequest, secondResponse, secondChain);

        assertEquals(429, secondResponse.getStatus());
        assertEquals("60", secondResponse.getHeader("Retry-After"));
        assertTrue(secondResponse.getContentAsString().contains("Too many authentication requests"));
        assertFalse(secondResponse.getContentAsString().contains("second-secret"));
        assertNull(secondChain.getRequest());
    }

    private static MockHttpServletRequest loginRequest(String remoteAddress, String forwardedFor, String password) {
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/auth/login");
        request.setServletPath("/api/auth/login");
        request.setRemoteAddr(remoteAddress);
        request.addHeader("X-Forwarded-For", forwardedFor);
        request.setContent(("{\"usernameOrEmail\":\"preview\",\"password\":\"" + password + "\"}").getBytes());
        return request;
    }
}
