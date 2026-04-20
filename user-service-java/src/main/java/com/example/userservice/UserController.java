package com.example.userservice;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/users")
public class UserController {

    private final UserService svc;

    public UserController(UserService svc) {
        this.svc = svc;
    }

    // ---- health ----

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "ok", "service", "user-service");
    }

    // ---- register ----

    record RegisterRequest(String name, String email, String password) {}

    @PostMapping("/register")
    public ResponseEntity<Map<String, Object>> register(@RequestBody RegisterRequest req) {
        User user = svc.register(req.name(), req.email(), req.password());
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(Map.of(
                        "id",    user.getId(),
                        "name",  user.getName(),
                        "email", user.getEmail()
                ));
    }

    // ---- login ----

    record LoginRequest(String email, String password) {}

    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody LoginRequest req) {
        User user = svc.login(req.email(), req.password());
        return Map.of(
                "id",    user.getId(),
                "name",  user.getName(),
                "email", user.getEmail(),
                "message", "Login successful"
        );
    }

    // ---- get profile ----

    @GetMapping("/{id}")
    public Map<String, Object> getUser(@PathVariable Long id) {
        User user = svc.findById(id);
        return Map.of(
                "id",        user.getId(),
                "name",      user.getName(),
                "email",     user.getEmail(),
                "createdAt", user.getCreatedAt().toString()
        );
    }

    // ---- portfolio (stub — wire to trading-service later) ----

    @GetMapping("/{id}/portfolio")
    public Map<String, Object> getPortfolio(@PathVariable Long id) {
        // Confirm the user exists first
        svc.findById(id);
        // TODO: call trading-service to fetch real trades
        return Map.of(
                "userId",  id,
                "message", "Portfolio endpoint ready — connect to trading-service for real data",
                "holdings", java.util.List.of()
        );
    }
}
