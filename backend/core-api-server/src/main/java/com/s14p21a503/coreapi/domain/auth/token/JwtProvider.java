package com.s14p21a503.coreapi.domain.auth.token;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.auth.security.PrincipalDetailsService;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.stereotype.Component;

import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.GeneralSecurityException;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.InvalidKeySpecException;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.time.Instant;
import java.util.Base64;
import java.util.Date;

@Component
public class JwtProvider {

    private final PrincipalDetailsService principalDetailsService;
    private final ResourceLoader resourceLoader;

    @Value("${jwt.private-key-path}")
    private String privateKeyPath;

    @Value("${jwt.public-key-path}")
    private String publicKeyPath;

    @Value("${jwt.issuer}")
    private String issuer;

    @Value("${jwt.access-expiration}")
    private long accessExpiration;

    @Value("${jwt.refresh-expiration}")
    private long refreshExpiration;

    private RSAPrivateKey privateKey;
    private RSAPublicKey publicKey;

    public JwtProvider(PrincipalDetailsService principalDetailsService, ResourceLoader resourceLoader) {
        this.principalDetailsService = principalDetailsService;
        this.resourceLoader = resourceLoader;
    }

    @PostConstruct
    private void initKey() {
        try {
            this.privateKey = loadPrivateKey(privateKeyPath);
            this.publicKey = loadPublicKey(publicKeyPath);
        } catch (IOException | GeneralSecurityException e) {
            throw new IllegalStateException("Failed to initialize RSA JWT keys.", e);
        }
    }

    public String createAccessToken(Long userId) {
        return createToken(userId, accessExpiration);
    }

    public String createRefreshToken(Long userId) {
        return createToken(userId, refreshExpiration);
    }

    public boolean validateToken(String token) {
        if (token == null || token.isBlank()) {
            return false;
        }

        try {
            parseClaims(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }

    public Long getUserIdFromToken(String token) {
        try {
            Claims claims = parseClaims(token);
            return Long.parseLong(claims.getSubject());
        } catch (RuntimeException e) {
            throw new CustomException(ErrorCode.INVALID_TOKEN);
        }
    }

    public Authentication getAuthentication(String token) {
        Long userId = getUserIdFromToken(token);
        UserDetails userDetails = principalDetailsService.loadUserById(userId);
        return new UsernamePasswordAuthenticationToken(userDetails, null, userDetails.getAuthorities());
    }

    public long getAccessExpiration() {
        return accessExpiration;
    }

    public long getRefreshExpiration() {
        return refreshExpiration;
    }

    private String createToken(Long userId, long expiration) {
        Instant now = Instant.now();
        Instant expiresAt = now.plusMillis(expiration);

        return Jwts.builder()
                .subject(String.valueOf(userId))
                .issuer(issuer)
                .issuedAt(Date.from(now))
                .expiration(Date.from(expiresAt))
                .signWith(privateKey, Jwts.SIG.RS256)
                .compact();
    }

    private Claims parseClaims(String token) {
        return Jwts.parser()
                .verifyWith(publicKey)
                .requireIssuer(issuer)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    private RSAPrivateKey loadPrivateKey(String path) throws IOException, GeneralSecurityException {
        String pem = readPemContent(path);
        KeyFactory keyFactory = KeyFactory.getInstance("RSA");
        byte[] keyBytes = decodePem(pem);

        try {
            PrivateKey generated = keyFactory.generatePrivate(new PKCS8EncodedKeySpec(keyBytes));
            if (generated instanceof RSAPrivateKey rsaPrivateKey) {
                return rsaPrivateKey;
            }
            throw new GeneralSecurityException("Loaded private key is not an RSA private key.");
        } catch (InvalidKeySpecException e) {
            if (!pem.contains("BEGIN RSA PRIVATE KEY")) {
                throw e;
            }
            byte[] pkcs8Bytes = convertPkcs1ToPkcs8(keyBytes);
            PrivateKey generated = keyFactory.generatePrivate(new PKCS8EncodedKeySpec(pkcs8Bytes));
            if (generated instanceof RSAPrivateKey rsaPrivateKey) {
                return rsaPrivateKey;
            }
            throw new GeneralSecurityException("Loaded private key is not an RSA private key.");
        }
    }

    private RSAPublicKey loadPublicKey(String path) throws IOException, GeneralSecurityException {
        String pem = readPemContent(path);
        byte[] keyBytes = decodePem(pem);

        KeyFactory keyFactory = KeyFactory.getInstance("RSA");
        PublicKey generated = keyFactory.generatePublic(new X509EncodedKeySpec(keyBytes));
        if (generated instanceof RSAPublicKey rsaPublicKey) {
            return rsaPublicKey;
        }
        throw new GeneralSecurityException("Loaded public key is not an RSA public key.");
    }

    private String readPemContent(String path) throws IOException {
        String resourceLocation = resolveResourceLocation(path);
        Resource resource = resourceLoader.getResource(resourceLocation);
        if (!resource.exists()) {
            throw new FileNotFoundException("JWT key resource not found: " + resourceLocation);
        }

        try (InputStream inputStream = resource.getInputStream()) {
            return new String(inputStream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    private String resolveResourceLocation(String path) {
        if (path.startsWith("classpath:") || path.startsWith("file:")) {
            return path;
        }

        if (path.matches("^[a-zA-Z]:[\\\\/].*")) {
            return "file:" + Path.of(path).toAbsolutePath().normalize();
        }
        if (path.startsWith("/")) {
            return "file:" + Path.of(path).toAbsolutePath().normalize();
        }

        return "classpath:" + path;
    }

    private byte[] decodePem(String pem) {
        String normalized = pem
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replace("-----BEGIN RSA PRIVATE KEY-----", "")
                .replace("-----END RSA PRIVATE KEY-----", "")
                .replace("-----BEGIN PUBLIC KEY-----", "")
                .replace("-----END PUBLIC KEY-----", "")
                .replaceAll("\\s+", "");
        return Base64.getDecoder().decode(normalized);
    }

    private byte[] convertPkcs1ToPkcs8(byte[] pkcs1Bytes) {
        byte[] rsaAlgorithmIdentifier = new byte[]{
                0x30, 0x0D,
                0x06, 0x09, 0x2A, (byte) 0x86, 0x48, (byte) 0x86, (byte) 0xF7, 0x0D, 0x01, 0x01, 0x01,
                0x05, 0x00
        };
        byte[] version = new byte[]{0x02, 0x01, 0x00};
        byte[] privateKeyOctetString = concat(new byte[]{0x04}, encodeLength(pkcs1Bytes.length), pkcs1Bytes);
        byte[] sequenceBody = concat(version, rsaAlgorithmIdentifier, privateKeyOctetString);
        return concat(new byte[]{0x30}, encodeLength(sequenceBody.length), sequenceBody);
    }

    private byte[] encodeLength(int length) {
        if (length < 128) {
            return new byte[]{(byte) length};
        }

        int temp = length;
        int numBytes = 0;
        while (temp > 0) {
            temp >>= 8;
            numBytes++;
        }

        byte[] encoded = new byte[numBytes + 1];
        encoded[0] = (byte) (0x80 | numBytes);
        for (int i = numBytes; i > 0; i--) {
            encoded[i] = (byte) (length & 0xFF);
            length >>= 8;
        }
        return encoded;
    }

    private byte[] concat(byte[]... arrays) {
        int totalLength = 0;
        for (byte[] array : arrays) {
            totalLength += array.length;
        }

        byte[] result = new byte[totalLength];
        int offset = 0;
        for (byte[] array : arrays) {
            System.arraycopy(array, 0, result, offset, array.length);
            offset += array.length;
        }
        return result;
    }
}
