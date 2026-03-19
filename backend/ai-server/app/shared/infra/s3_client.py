import os
import boto3
import logging
from typing import Optional
from botocore.exceptions import ClientError

import warnings
from cryptography.utils import CryptographyDeprecationWarning
warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

logger = logging.getLogger(__name__)

class S3Client:
    """AWS S3 연동을 위한 싱글톤 클라이언트 유틸리티."""
    
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(S3Client, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.access_key = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
        self.secret_key = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
        self.region = (os.getenv("AWS_REGION") or "ap-northeast-2").strip()
        self.bucket_name = (os.getenv("S3_BUCKET_NAME") or "").strip()
        self.path_prefix = (os.getenv("S3_PATH_PREFIX") or "").strip("/")
        
        
        if not self.access_key or not self.secret_key:
            logger.warning("S3 자격 증명이 설정되지 않았습니다. .env 파일을 확인하세요.")
            self.client = None
        else:
            try:
                self.client = boto3.client(
                    "s3",
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region,
                )
                self._initialized = True
                logger.info("S3Client 초기화 완료 (Bucket: %s)", self.bucket_name)
            except Exception as e:
                logger.error("S3Client 초기화 실패: %s", str(e))
                self.client = None

    def upload_file(self, local_path: str, s3_key: str) -> bool:
        """로컬 파일을 S3로 업로드합니다.
        
        Args:
            local_path: 로컬 파일 경로
            s3_key: S3 내 저장될 키 (경로)
        """
        if not self.client:
            logger.error("S3 클라이언트가 초기화되지 않아 업로드할 수 없습니다.")
            return False
            
        # 프레고 접두사(tlu600/)가 있다면 결합
        full_key = f"{self.path_prefix}/{s3_key.lstrip('/')}" if self.path_prefix else s3_key
        
        try:
            self.client.upload_file(local_path, self.bucket_name, full_key)
            logger.info("S3 업로드 성공: %s -> s3://%s/%s", local_path, self.bucket_name, full_key)
            return True
        except ClientError as e:
            logger.error("S3 업로드 실패: %s", e)
            return False

    def download_file(self, s3_key: str, local_path: str) -> bool:
        """S3 파일을 로컬로 다운로드합니다."""
        if not self.client:
            return False
            
        full_key = f"{self.path_prefix}/{s3_key.lstrip('/')}" if self.path_prefix else s3_key
        
        try:
            self.client.download_file(self.bucket_name, full_key, local_path)
            logger.info("S3 다운로드 성공: s3://%s/%s -> %s", self.bucket_name, full_key, local_path)
            return True
        except ClientError as e:
            logger.error("S3 다운로드 실패: %s", e)
            return False

    def list_files(self, prefix: str = "") -> list:
        """특정 접두사 아래의 파일 목록을 반환합니다."""
        if not self.client:
            return []
            
        full_prefix = f"{self.path_prefix}/{prefix.lstrip('/')}" if self.path_prefix else prefix
        
        try:
            response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=full_prefix)
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
        except ClientError as e:
            logger.error("S3 목록 조회 실패: %s", e)
            return []

# 싱글톤 인스턴스 노출
s3_client = S3Client()
