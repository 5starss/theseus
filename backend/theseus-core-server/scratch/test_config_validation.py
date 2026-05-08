import os
import sys
from unittest.mock import patch
from pydantic import ValidationError

# 현재 디렉토리(backend/theseus-core-server)를 sys.path에 추가
sys.path.append(os.getcwd())

def test_prod_config_validation():
    print("Testing production configuration validation...")
    
    # Import Settings inside the function or after setting up path
    from src.config import Settings

    # 1. Invalid Prod Config (Mock Auth Enabled)
    print("\nCase 1: ENV=prod but AUTH_MODE=mock (Should fail)")
    env_vars = {
        "ENV": "prod",
        "AUTH_MODE": "mock",
        "ALLOWED_ORIGINS": '["https://myapp.com"]',
        "SPRING_BOOT_INTERNAL_API_KEY": "secure-key-123"
    }
    
    with patch.dict(os.environ, env_vars, clear=True):
        try:
            Settings()
            print("FAILED: Should have raised ValueError for mock auth in prod")
        except (ValueError, ValidationError) as e:
            print(f"PASSED: Caught expected error: {e}")

    # 2. Invalid Prod Config (Local URLs)
    print("\nCase 2: ENV=prod but contains localhost URLs (Should fail)")
    env_vars = {
        "ENV": "prod",
        "AUTH_MODE": "spring",
        "ALLOWED_ORIGINS": '["https://myapp.com"]',
        "SPRING_BOOT_INTERNAL_API_KEY": "secure-key-123",
        "SPRING_BOOT_INTERNAL_URL": "http://localhost:8080"
    }
    
    with patch.dict(os.environ, env_vars, clear=True):
        try:
            Settings()
            print("FAILED: Should have raised ValueError for localhost URLs in prod")
        except (ValueError, ValidationError) as e:
            print(f"PASSED: Caught expected error: {e}")

    # 3. Valid Prod Config
    print("\nCase 3: Valid Production Config (Should pass)")
    env_vars = {
        "ENV": "prod",
        "AUTH_MODE": "spring",
        "ALLOWED_ORIGINS": '["https://myapp.com", "https://api.myapp.com"]',
        "SPRING_BOOT_INTERNAL_API_KEY": "actually-secure-key-change-this",
        "SPRING_BOOT_INTERNAL_URL": "http://api-server:8080",
        "SPRING_BOOT_AUTH_VERIFY_URL": "http://api-server:8080/api/internal/auth/verify",
        "SPRING_BOOT_PROJECT_PERMISSIONS_URL": "http://api-server:8080/api/internal/project/permissions",
        "SPRING_BOOT_BILLING_USAGE_URL": "http://api-server:8080/api/internal/billing/usage",
        "SPRING_BOOT_TOOL_PLAN_URL": "http://api-server:8080/api/internal/tool-plan/save",
        "SPRING_BOOT_INTERNAL_HISTORY_MESSAGES_URL": "http://api-server:8080/api/internal/history/messages"
    }
    
    with patch.dict(os.environ, env_vars, clear=True):
        try:
            s = Settings()
            print("PASSED: Valid production configuration accepted")
            print(f"Parsed Allowed Origins: {s.cors_allowed_origins}")
        except Exception as e:
            print(f"FAILED: Should have accepted valid config: {e}")

if __name__ == "__main__":
    test_prod_config_validation()
