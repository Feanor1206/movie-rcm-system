package com.dippie.moviercm.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Component
public class AuthAdmissionFilter extends OncePerRequestFilter {

    private static final String RATE_LIMIT_BODY = "{\"success\":false,\"error\":\"Too many authentication requests\",\"message\":\"Please retry later.\"}";

    private final AuthAdmissionService admissionService;

    public AuthAdmissionFilter(AuthAdmissionService admissionService) {
        this.admissionService = admissionService;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        AuthAdmissionService.Endpoint endpoint = endpointFor(request);
        if (endpoint != null) {
            AuthAdmissionService.Admission admission = admissionService.tryAdmit(request.getRemoteAddr(), endpoint);
            if (!admission.allowed()) {
                response.setStatus(429);
                response.setHeader("Retry-After", Long.toString(admission.retryAfterSeconds()));
                response.setHeader("Cache-Control", "no-store");
                response.setContentType(MediaType.APPLICATION_JSON_VALUE);
                response.setCharacterEncoding("UTF-8");
                response.getWriter().write(RATE_LIMIT_BODY);
                return;
            }
        }
        filterChain.doFilter(request, response);
    }

    private static AuthAdmissionService.Endpoint endpointFor(HttpServletRequest request) {
        if (!HttpMethod.POST.matches(request.getMethod())) {
            return null;
        }
        String path = request.getServletPath();
        if ("/api/auth/login".equals(path) || "/api/auth/login/".equals(path)) {
            return AuthAdmissionService.Endpoint.LOGIN;
        }
        if ("/api/auth/register".equals(path) || "/api/auth/register/".equals(path)) {
            return AuthAdmissionService.Endpoint.REGISTER;
        }
        return null;
    }
}
