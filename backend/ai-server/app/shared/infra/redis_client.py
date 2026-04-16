import os
import logging
import redis
from typing import Optional
from sshtunnel import SSHTunnelForwarder

logger = logging.getLogger(__name__)

class RedisClient:
    """Redis 연동 및 SSH 터널링을 지원하는 싱글톤 클라이언트."""
    
    _instance = None
    _client = None
    _tunnel = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.host = os.getenv("REDIS_HOST", "redis")
        self.port = int(os.getenv("REDIS_PORT", "6379"))
        self.password = os.getenv("REDIS_PASSWORD", None)
        self.use_ssh = os.getenv("USE_SSH", "false").lower() == "true"
        self._initialized = True

    def get_client(self) -> redis.Redis:
        """연결된 Redis 클라이언트를 반환합니다. 필요시 터널을 생성합니다."""
        if self._client:
            try:
                self._client.ping()
                return self._client
            except Exception:
                logger.info("Redis 연결 끊김 감지. 재연결 시도 중...")
                self.close()

        if self.use_ssh:
            ssh_host = os.getenv("SSH_HOST")
            ssh_port = int(os.getenv("SSH_PORT", "22"))
            ssh_user = os.getenv("SSH_USER")
            ssh_password = os.getenv("SSH_PASSWORD")
            ssh_key_path = os.getenv("SSH_KEY_PATH")

            if not ssh_host:
                logger.warning("USE_SSH=true 이지만 SSH_HOST 설정이 없어 직접 연결을 시도합니다.")
                return self._direct_connect()

            logger.info("Redis SSH 터널링 시도 (%s:%d -> %s:%d)", ssh_host, ssh_port, self.host, self.port)
            
            try:
                tunnel_kwargs = {
                    "ssh_address_or_host": (ssh_host, ssh_port),
                    "ssh_username": ssh_user,
                    "remote_bind_address": (self.host, self.port),
                }
                if ssh_key_path and os.path.exists(ssh_key_path):
                    tunnel_kwargs["ssh_pkey"] = ssh_key_path
                elif ssh_password:
                    tunnel_kwargs["ssh_password"] = ssh_password

                self._tunnel = SSHTunnelForwarder(**tunnel_kwargs)
                self._tunnel.start()
                
                self._client = redis.Redis(
                    host="127.0.0.1",
                    port=self._tunnel.local_bind_port,
                    password=self.password,
                    decode_responses=True,
                    socket_timeout=5
                )
            except Exception as e:
                logger.error("Redis SSH 터널링 실패: %s", e)
                return self._direct_connect()
        else:
            return self._direct_connect()
            
        return self._client

    def _direct_connect(self) -> redis.Redis:
        logger.info("Redis 직접 연결 시도 (%s:%d)", self.host, self.port)
        self._client = redis.Redis(
            host=self.host,
            port=self.port,
            password=self.password,
            decode_responses=True,
            socket_timeout=5
        )
        return self._client

    def close(self):
        """연결 및 터널을 닫습니다."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        if self._tunnel:
            try:
                self._tunnel.stop()
            except Exception:
                pass
            self._tunnel = None

# 싱글톤 인스턴스 노출
redis_client = RedisClient()
