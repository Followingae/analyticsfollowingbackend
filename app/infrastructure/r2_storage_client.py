"""
Cloudflare R2 Storage Client
High-performance S3-compatible storage client for CDN image system
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import hashlib
import io

logger = logging.getLogger(__name__)

class R2StorageClient:
    """Cloudflare R2 storage client using S3 compatibility"""
    
    def __init__(self, account_id: str, access_key: str, secret_key: str, bucket_name: str):
        self.bucket_name = bucket_name
        self.account_id = account_id
        
        # R2 S3-compatible endpoint
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        
        # Handle shorter access keys from User API tokens
        if len(access_key) < 20:
            logger.warning("Using User API token - may need R2-specific token for full functionality")
        
        # Configure with optimized settings for R2
        config = Config(
            region_name='auto',  # R2 uses 'auto' region
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            max_pool_connections=50
        )
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=config
        )
        
        self.stats = {
            'uploads_successful': 0,
            'uploads_failed': 0,
            'downloads_successful': 0,
            'downloads_failed': 0,
            'total_bytes_uploaded': 0,
            'total_bytes_downloaded': 0
        }
        
        logger.info(f"R2 client initialized for bucket: {bucket_name}")
        # Test connection will be done on first use to avoid blocking initialization
    
    def test_connection(self):
        """Test R2 connection and bucket access"""
        try:
            # Test bucket access
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ R2 bucket '{self.bucket_name}' is accessible")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"❌ R2 bucket '{self.bucket_name}' not found")
            elif error_code == '403':
                logger.error(f"❌ Access denied to R2 bucket '{self.bucket_name}'")
            else:
                logger.error(f"❌ R2 connection test failed: {e}")
            return False
    
    async def upload_object(self, key: str, content: bytes, content_type: str, 
                          cache_control: str = None, metadata: Dict[str, str] = None) -> bool:
        """Upload object to R2 with proper headers"""
        try:
            extra_args = {
                'ContentType': content_type
            }
            
            # Add cache control for immutable CDN caching
            if cache_control:
                extra_args['CacheControl'] = cache_control
            else:
                extra_args['CacheControl'] = 'public, max-age=31536000, immutable'
            
            # Add custom metadata
            if metadata:
                extra_args['Metadata'] = metadata
            
            # Add content hash for integrity verification
            content_hash = hashlib.sha256(content).hexdigest()
            extra_args['Metadata'] = extra_args.get('Metadata', {})
            extra_args['Metadata']['content-sha256'] = content_hash
            
            # Upload using put_object in executor for async compatibility
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=content,
                    **extra_args
                )
            )
            
            # Update stats
            self.stats['uploads_successful'] += 1
            self.stats['total_bytes_uploaded'] += len(content)
            
            logger.debug(f"✅ Uploaded {key} ({len(content)} bytes)")
            return True
            
        except ClientError as e:
            self.stats['uploads_failed'] += 1
            error_code = e.response['Error']['Code']
            logger.error(f"❌ R2 upload failed for {key}: {error_code} - {e}")
            return False
        except Exception as e:
            self.stats['uploads_failed'] += 1
            logger.error(f"❌ Unexpected error uploading {key}: {e}")
            return False
    
    async def object_exists(self, key: str) -> bool:
        """Check if object exists in R2"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"❌ Error checking object existence {key}: {e}")
            return False
    
    async def delete_object(self, key: str) -> bool:
        """Delete object from R2"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            )
            logger.info(f"🗑️ Deleted object: {key}")
            return True
        except ClientError as e:
            logger.error(f"❌ Error deleting object {key}: {e}")
            return False
    
    async def get_object_metadata(self, key: str) -> Dict[str, Any]:
        """Get object metadata from R2"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            )
            return {
                'content_length': response.get('ContentLength'),
                'content_type': response.get('ContentType'),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"'),
                'cache_control': response.get('CacheControl'),
                'metadata': response.get('Metadata', {}),
                'storage_class': response.get('StorageClass', 'STANDARD')
            }
        except ClientError as e:
            logger.error(f"❌ Error getting metadata for {key}: {e}")
            return {}
    
    async def download_object(self, key: str) -> Optional[bytes]:
        """Download object from R2"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            )
            
            content = response['Body'].read()
            self.stats['downloads_successful'] += 1
            self.stats['total_bytes_downloaded'] += len(content)
            
            logger.debug(f"📥 Downloaded {key} ({len(content)} bytes)")
            return content
            
        except ClientError as e:
            self.stats['downloads_failed'] += 1
            logger.error(f"❌ Error downloading {key}: {e}")
            return None
    
    async def batch_upload(self, objects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Efficiently upload multiple objects in batch
        
        Args:
            objects: List of dicts with 'key', 'content', 'content_type' keys
        """
        results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        # Upload objects concurrently
        upload_tasks = []
        for obj in objects:
            task = self.upload_object(
                key=obj['key'],
                content=obj['content'],
                content_type=obj['content_type'],
                cache_control=obj.get('cache_control'),
                metadata=obj.get('metadata')
            )
            upload_tasks.append(task)
        
        # Execute uploads concurrently
        upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)
        
        for i, result in enumerate(upload_results):
            if isinstance(result, Exception):
                results['failed'] += 1
                results['errors'].append({
                    'key': objects[i]['key'],
                    'error': str(result)
                })
            elif result:
                results['successful'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({
                    'key': objects[i]['key'],
                    'error': 'Upload failed'
                })
        
        logger.info(f"📤 Batch upload completed: {results['successful']}/{len(objects)} successful")
        return results
    
    async def list_objects(self, prefix: str = "", max_keys: int = 1000) -> List[Dict[str, Any]]:
        """List objects in bucket with optional prefix filter"""
        try:
            loop = asyncio.get_event_loop()
            
            kwargs = {
                'Bucket': self.bucket_name,
                'MaxKeys': max_keys
            }
            if prefix:
                kwargs['Prefix'] = prefix
            
            response = await loop.run_in_executor(
                None,
                lambda: self.s3_client.list_objects_v2(**kwargs)
            )
            
            objects = []
            for obj in response.get('Contents', []):
                objects.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag'].strip('"'),
                    'storage_class': obj.get('StorageClass', 'STANDARD')
                })
            
            return objects
            
        except ClientError as e:
            logger.error(f"❌ Error listing objects: {e}")
            return []
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get basic storage statistics"""
        try:
            # Get bucket info
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, 
                MaxKeys=1000
            )
            
            object_count = response.get('KeyCount', 0)
            total_size = sum(obj.get('Size', 0) for obj in response.get('Contents', []))
            
            return {
                'bucket_name': self.bucket_name,
                'object_count': object_count,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / 1024 / 1024, 2),
                'total_size_gb': round(total_size / 1024 / 1024 / 1024, 3),
                'client_stats': self.stats.copy(),
                'last_checked': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting storage stats: {e}")
            return {
                'error': str(e),
                'client_stats': self.stats.copy()
            }
    
    def generate_presigned_url(self, key: str, expiration: int = 3600) -> Optional[str]:
        """Generate presigned URL for direct access (if needed)"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"❌ Error generating presigned URL for {key}: {e}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for R2 connectivity"""
        health_status = {
            'status': 'healthy',
            'bucket_accessible': False,
            'upload_test': False,
            'download_test': False,
            'latency_ms': None,
            'error': None
        }
        
        try:
            import time
            
            # Test bucket access
            start_time = time.time()
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            health_status['bucket_accessible'] = True
            
            # Test upload/download with small test object
            test_key = f"health-check/{datetime.utcnow().isoformat()}.txt"
            test_content = b"R2 health check test content"
            
            # Upload test
            upload_success = await self.upload_object(
                key=test_key,
                content=test_content,
                content_type='text/plain'
            )
            health_status['upload_test'] = upload_success
            
            # Download test
            if upload_success:
                downloaded_content = await self.download_object(test_key)
                health_status['download_test'] = downloaded_content == test_content
                
                # Cleanup test object
                await self.delete_object(test_key)
            
            # Calculate latency
            end_time = time.time()
            health_status['latency_ms'] = round((end_time - start_time) * 1000, 2)
            
            # Overall status
            if not (health_status['bucket_accessible'] and 
                   health_status['upload_test'] and 
                   health_status['download_test']):
                health_status['status'] = 'degraded'
                
        except Exception as e:
            health_status['status'] = 'unhealthy'
            health_status['error'] = str(e)
            logger.error(f"❌ R2 health check failed: {e}")
        
        return health_status


class R2StorageError(Exception):
    """Custom exception for R2 storage operations"""
    pass


class R2ConnectionError(R2StorageError):
    """Exception for R2 connection issues"""
    pass


class R2UploadError(R2StorageError):
    """Exception for R2 upload failures"""
    pass


# Global storage client instance
r2_storage_client: Optional[R2StorageClient] = None