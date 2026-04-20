package com.example.userservice;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "users")
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(unique = true, nullable = false, length = 100)
    private String email;

    @Column(nullable = false, length = 100)
    private String name;

    /** Stored as a BCrypt hash — never store plaintext passwords. */
    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt = LocalDateTime.now();

    // ---- getters / setters ----

    public Long getId()                      { return id; }
    public String getEmail()                 { return email; }
    public void   setEmail(String email)     { this.email = email; }
    public String getName()                  { return name; }
    public void   setName(String name)       { this.name = name; }
    public String getPasswordHash()          { return passwordHash; }
    public void   setPasswordHash(String h)  { this.passwordHash = h; }
    public LocalDateTime getCreatedAt()      { return createdAt; }
}
