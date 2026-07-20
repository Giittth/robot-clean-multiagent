"""云存储工具：上传清扫地图等文件到对象存储（S3/OSS/COS）"""
import os
from typing import Optional, Dict, Any
from backend.agents.tools.base_tool import BaseTool, ToolResult
from backend.utils.logger_handler import logger


class CloudStorageTool(BaseTool):
    """上传文件（清扫地图、日志等）到云对象存储，支持 S3、阿里云 OSS、腾讯云 COS。"""

    name = "cloud_storage"
    description = "上传文件（清扫地图图片、日志等）到云存储，支持 S3、阿里云 OSS、腾讯云 COS"
    parameters = {
        "file_path": {
            "type": "string",
            "description": "本地文件路径，如 /data/maps/latest_map.png",
            "required": True,
        },
        "object_key": {
            "type": "string",
            "description": "云端存储路径（key），默认自动生成基于日期的路径",
        },
        "provider": {
            "type": "string",
            "enum": ["s3", "oss", "cos", "auto"],
            "description": "云存储提供商：s3=AWS S3, oss=阿里云OSS, cos=腾讯云COS, auto=自动检测配置",
        },
        "bucket": {
            "type": "string",
            "description": "存储桶名称，默认从环境变量读取",
        },
        "make_public": {
            "type": "boolean",
            "description": "是否生成公开访问 URL",
        },
    }

    def __init__(
        self,
        s3_config: Optional[Dict[str, str]] = None,
        oss_config: Optional[Dict[str, str]] = None,
        cos_config: Optional[Dict[str, str]] = None,
    ):
        """
        Args:
            s3_config: AWS S3 配置 {"region", "bucket", "access_key", "secret_key", "endpoint"}（可选）
            oss_config: 阿里云 OSS 配置 {"endpoint", "bucket", "access_key", "secret_key"}（可选）
            cos_config: 腾讯云 COS 配置 {"region", "bucket", "secret_id", "secret_key"}（可选）
        """
        self._s3_config = s3_config or {}
        self._oss_config = oss_config or {}
        self._cos_config = cos_config or {}

    async def execute(
        self,
        file_path: str = "",
        object_key: str = "",
        provider: str = "auto",
        bucket: str = "",
        make_public: bool = False,
        **kwargs,
    ) -> ToolResult:
        try:
            if not os.path.isfile(file_path):
                return ToolResult(success=False, error=f"文件不存在: {file_path}")

            file_size = os.path.getsize(file_path)
            if file_size <= 0:
                return ToolResult(success=False, error=f"文件为空: {file_path}")

            if not object_key:
                from datetime import datetime
                base_name = os.path.basename(file_path)
                date_str = datetime.now().strftime("%Y/%m/%d")
                object_key = f"uploads/{date_str}/{base_name}"

            effective_provider = self._detect_provider(provider)

            if effective_provider == "s3":
                return await self._upload_to_s3(file_path, object_key, bucket, make_public)
            elif effective_provider == "oss":
                return await self._upload_to_oss(file_path, object_key, bucket, make_public)
            elif effective_provider == "cos":
                return await self._upload_to_cos(file_path, object_key, bucket, make_public)
            else:
                logger.info(f"[CloudStorage SIM] upload {file_path} -> {object_key}")
                return ToolResult(success=True, data={
                    "answer": f"已将 {os.path.basename(file_path)} 上传至云存储 ({effective_provider})",
                    "object_key": object_key,
                    "file_size": file_size,
                    "url": f"https://{bucket or 'my-bucket'}.s3.amazonaws.com/{object_key}",
                    "simulated": True,
                })

        except Exception as e:
            logger.error(f"CloudStorage tool failed: {e}")
            return ToolResult(success=False, error=f"云存储上传失败: {e}")

    def _detect_provider(self, preferred: str) -> str:
        if preferred != "auto":
            return preferred
        if self._s3_config:
            return "s3"
        if self._oss_config:
            return "oss"
        if self._cos_config:
            return "cos"
        return "s3"

    async def _upload_to_s3(self, file_path: str, object_key: str, bucket: str, public: bool) -> ToolResult:
        try:
            import boto3
            from botocore.exceptions import ClientError

            cfg = self._s3_config
            session = boto3.Session(
                aws_access_key_id=cfg.get("access_key") or os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=cfg.get("secret_key") or os.environ.get("AWS_SECRET_ACCESS_KEY"),
                region_name=cfg.get("region") or os.environ.get("AWS_REGION", "us-east-1"),
            )
            s3 = session.client("s3", endpoint_url=cfg.get("endpoint"))

            actual_bucket = bucket or cfg.get("bucket") or os.environ.get("AWS_S3_BUCKET")
            if not actual_bucket:
                return ToolResult(success=False, error="未指定 S3 bucket，请通过参数或环境变量 AWS_S3_BUCKET 设置")

            extra_args: Dict[str, Any] = {}
            if public:
                extra_args["ACL"] = "public-read"

            with open(file_path, "rb") as f:
                s3.upload_fileobj(f, actual_bucket, object_key, ExtraArgs=extra_args or None)

            url = f"https://{actual_bucket}.s3.amazonaws.com/{object_key}"

            return ToolResult(success=True, data={
                "answer": f"已上传至 S3: {object_key}",
                "object_key": object_key,
                "bucket": actual_bucket,
                "url": url,
                "public": public,
            })

        except ImportError:
            return ToolResult(success=False, error="boto3 未安装 (pip install boto3)")
        except ClientError as e:
            return ToolResult(success=False, error=f"S3 上传失败: {e}")

    async def _upload_to_oss(self, file_path: str, object_key: str, bucket: str, public: bool) -> ToolResult:
        try:
            import oss2

            cfg = self._oss_config
            auth = oss2.Auth(
                cfg.get("access_key") or os.environ.get("OSS_ACCESS_KEY_ID", ""),
                cfg.get("secret_key") or os.environ.get("OSS_ACCESS_KEY_SECRET", ""),
            )
            endpoint = cfg.get("endpoint") or os.environ.get("OSS_ENDPOINT", "")
            actual_bucket = bucket or cfg.get("bucket") or os.environ.get("OSS_BUCKET", "")

            if not actual_bucket or not endpoint:
                return ToolResult(success=False, error="OSS 配置不完整，需提供 endpoint 和 bucket")

            bucket_obj = oss2.Bucket(auth, endpoint, actual_bucket)
            with open(file_path, "rb") as f:
                result = bucket_obj.put_object(object_key, f)

            if result.status != 200:
                return ToolResult(success=False, error=f"OSS 上传失败: HTTP {result.status}")

            url = f"https://{actual_bucket}.{endpoint}/{object_key}"

            return ToolResult(success=True, data={
                "answer": f"已上传至 OSS: {object_key}",
                "object_key": object_key,
                "bucket": actual_bucket,
                "url": url,
                "public": public,
            })

        except ImportError:
            return ToolResult(success=False, error="oss2 未安装 (pip install oss2)")
        except Exception as e:
            return ToolResult(success=False, error=f"OSS 上传失败: {e}")

    async def _upload_to_cos(self, file_path: str, object_key: str, bucket: str, public: bool) -> ToolResult:
        try:
            from qcloud_cos import CosConfig, CosS3Client

            cfg = self._cos_config
            secret_id = cfg.get("secret_id") or os.environ.get("COS_SECRET_ID", "")
            secret_key = cfg.get("secret_key") or os.environ.get("COS_SECRET_KEY", "")
            region = cfg.get("region") or os.environ.get("COS_REGION", "ap-guangzhou")
            actual_bucket = bucket or cfg.get("bucket") or os.environ.get("COS_BUCKET", "")

            if not actual_bucket:
                return ToolResult(success=False, error="未指定 COS bucket")

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
            client = CosS3Client(config)

            with open(file_path, "rb") as f:
                response = client.put_object(
                    Bucket=actual_bucket,
                    Body=f,
                    Key=object_key,
                )

            url = f"https://{actual_bucket}.cos.{region}.myqcloud.com/{object_key}"

            return ToolResult(success=True, data={
                "answer": f"已上传至 COS: {object_key}",
                "object_key": object_key,
                "bucket": actual_bucket,
                "url": url,
                "public": public,
            })

        except ImportError:
            return ToolResult(success=False, error="cos-python-sdk-v5 未安装 (pip install cos-python-sdk-v5)")
        except Exception as e:
            return ToolResult(success=False, error=f"COS 上传失败: {e}")
