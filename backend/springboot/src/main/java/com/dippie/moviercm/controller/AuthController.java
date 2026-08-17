package com.dippie.moviercm.controller;

import com.dippie.moviercm.dto.ApiResponse;
import com.dippie.moviercm.dto.AuthRequest;
import com.dippie.moviercm.dto.AuthResponse;
import com.dippie.moviercm.dto.RegisterRequest;
import com.dippie.moviercm.dto.UserResponse;
import com.dippie.moviercm.security.UserDetailsImpl;
import com.dippie.moviercm.service.AuthService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @PostMapping("/login")
    public ResponseEntity<ApiResponse<AuthResponse>> login(@Valid @RequestBody AuthRequest loginRequest) {
        AuthResponse response = authService.login(loginRequest);
        return ResponseEntity.ok(ApiResponse.success("Login successful", response));
    }

    @PostMapping("/register")
    public ResponseEntity<ApiResponse<AuthResponse>> register(@Valid @RequestBody RegisterRequest registerRequest) {
        AuthResponse response = authService.register(registerRequest);
        return ResponseEntity.ok(ApiResponse.success("User registered successfully", response));
    }

    @GetMapping("/me")
    public ResponseEntity<ApiResponse<UserResponse>> getCurrentUser(@AuthenticationPrincipal UserDetailsImpl userDetails) {
        UserResponse response = authService.getCurrentUser(userDetails);
        return ResponseEntity.ok(ApiResponse.success("User profile fetched successfully", response));
    }
}
