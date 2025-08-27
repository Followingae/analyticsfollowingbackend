"""
Image Transcoder Service
High-performance image processing service for CDN system
"""
import httpx
import hashlib
from PIL import Image, ImageOps
import io
import time
import logging
from typing import Tuple, Dict, Any, List, Optional
from datetime import datetime
import asyncio
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ProcessingResult:
    """Result of image processing operation"""
    success: bool
    derivatives: Dict[int, Dict[str, Any]] = None
    error: str = ""
    processing_stats: Dict[str, Any] = None

class ProcessingError(Exception):
    """Custom exception for image processing errors"""
    pass

class ImageTranscoderService:
    """High-performance image processing service"""
    
    def __init__(self, r2_client):
        self.r2_client = r2_client
        
        # HTTP client optimized for image downloads
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            headers={
                'User-Agent': 'AnalyticsFollowing-CDN/1.0 (Image Processor)'
            }
        )
        
        # Processing stats
        self.stats = {
            'jobs_processed': 0,
            'jobs_failed': 0,
            'total_download_time_ms': 0,
            'total_processing_time_ms': 0,
            'total_upload_time_ms': 0,
            'bytes_processed': 0
        }
        
        # Supported formats and quality settings
        self.SUPPORTED_INPUT_FORMATS = {'JPEG', 'PNG', 'WEBP', 'BMP', 'TIFF'}
        self.OUTPUT_FORMAT = 'WEBP'
        self.OUTPUT_QUALITY = 85
        self.OUTPUT_METHOD = 6  # Best WebP compression
        
        logger.info("🖼️ Image Transcoder Service initialized")
    
    async def process_job(self, job_data: Dict[str, Any]) -> ProcessingResult:
        """Process a single CDN image job"""
        start_time = time.time()
        
        try:
            asset_id = job_data.get('asset_id')
            source_url = job_data.get('source_url')
            target_sizes = job_data.get('target_sizes', [256, 512])
            profile_id = job_data.get('profile_id')
            media_id = job_data.get('media_id', 'unknown')
            
            logger.info(f"🔄 Processing job for asset {asset_id}: {source_url}")
            
            # 1. Download original image
            download_start = time.time()
            original_data, download_info = await self._download_image(source_url)
            download_time = int((time.time() - download_start) * 1000)
            
            # 2. Load and validate image
            processing_start = time.time()
            original_image = await self._load_and_validate_image(original_data)
            
            # 3. Generate derivatives
            derivatives = await self._generate_derivatives(original_image, target_sizes)
            processing_time = int((time.time() - processing_start) * 1000)
            
            # 4. Upload to R2
            upload_start = time.time()
            upload_results = await self._upload_derivatives(
                derivatives, profile_id, media_id
            )
            upload_time = int((time.time() - upload_start) * 1000)
            
            total_time = int((time.time() - start_time) * 1000)
            
            # Update stats
            self.stats['jobs_processed'] += 1
            self.stats['total_download_time_ms'] += download_time
            self.stats['total_processing_time_ms'] += processing_time
            self.stats['total_upload_time_ms'] += upload_time
            self.stats['bytes_processed'] += len(original_data)
            
            logger.info(f"✅ Job completed in {total_time}ms: {len(derivatives)} derivatives")
            
            return ProcessingResult(
                success=True,
                derivatives=upload_results,
                processing_stats={
                    'download_time_ms': download_time,
                    'processing_time_ms': processing_time,
                    'upload_time_ms': upload_time,
                    'total_time_ms': total_time,
                    'original_size_bytes': len(original_data),
                    'original_dimensions': f"{original_image.width}x{original_image.height}",
                    'derivatives_count': len(derivatives),
                    'download_info': download_info
                }
            )
            
        except Exception as e:
            self.stats['jobs_failed'] += 1
            total_time = int((time.time() - start_time) * 1000)
            
            logger.error(f"❌ Job processing failed: {e}")
            return ProcessingResult(
                success=False,
                error=str(e),
                processing_stats={'total_time_ms': total_time}
            )
    
    async def _download_image(self, url: str) -> Tuple[bytes, Dict[str, Any]]:
        """Download image with error handling and metadata extraction"""
        try:
            logger.debug(f"📥 Downloading image: {url}")
            
            response = await self.session.get(url, follow_redirects=True)
            response.raise_for_status()
            
            # Extract metadata
            content_type = response.headers.get('content-type', 'image/jpeg')
            content_length = len(response.content)
            etag = response.headers.get('etag')
            last_modified = response.headers.get('last-modified')
            
            # Validate content type
            if not content_type.startswith('image/'):
                raise ProcessingError(f"Invalid content type: {content_type}")
            
            # Validate file size (max 50MB)
            if content_length > 50 * 1024 * 1024:
                raise ProcessingError(f"Image too large: {content_length} bytes")
            
            # Validate minimum size (at least 1KB)
            if content_length < 1024:
                raise ProcessingError(f"Image too small: {content_length} bytes")
            
            download_info = {
                'content_type': content_type,
                'content_length': content_length,
                'etag': etag,
                'last_modified': last_modified,
                'final_url': str(response.url)  # After redirects
            }
            
            logger.debug(f"✅ Downloaded {content_length} bytes")
            return response.content, download_info
            
        except httpx.TimeoutException:
            raise ProcessingError(f"Download timeout for URL: {url}")
        except httpx.HTTPStatusError as e:
            raise ProcessingError(f"HTTP {e.response.status_code} downloading {url}")
        except Exception as e:
            raise ProcessingError(f"Download failed: {e}")
    
    async def _load_and_validate_image(self, image_data: bytes) -> Image.Image:
        """Load and validate image with format conversion"""
        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))
            
            # Validate format
            if image.format not in self.SUPPORTED_INPUT_FORMATS:
                raise ProcessingError(f"Unsupported image format: {image.format}")
            
            # Validate dimensions
            if image.width < 50 or image.height < 50:
                raise ProcessingError(f"Image too small: {image.width}x{image.height}")
            
            if image.width > 10000 or image.height > 10000:
                raise ProcessingError(f"Image too large: {image.width}x{image.height}")
            
            # Auto-rotate based on EXIF data
            image = ImageOps.exif_transpose(image)
            
            # Convert to RGB if necessary (for WebP conversion)
            if image.mode in ['RGBA', 'P']:
                # Create white background for transparency
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                
                # Composite with white background
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
                
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            logger.debug(f"🖼️ Image loaded: {image.width}x{image.height} {image.mode}")
            return image
            
        except Exception as e:
            raise ProcessingError(f"Failed to load image: {e}")
    
    async def _generate_derivatives(self, original_image: Image.Image, 
                                  target_sizes: List[int]) -> Dict[int, bytes]:
        """Generate resized derivatives with optimized quality"""
        derivatives = {}
        
        try:
            for size in target_sizes:
                # Resize maintaining aspect ratio with high-quality resampling
                resized = ImageOps.fit(
                    original_image, 
                    (size, size), 
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5)
                )
                
                # Convert to WebP with optimized settings
                output_buffer = io.BytesIO()
                resized.save(
                    output_buffer, 
                    format=self.OUTPUT_FORMAT,
                    quality=self.OUTPUT_QUALITY,
                    method=self.OUTPUT_METHOD,
                    optimize=True
                )
                
                derivatives[size] = output_buffer.getvalue()
                
                logger.debug(f"📐 Generated {size}px derivative: {len(derivatives[size])} bytes")
            
            return derivatives
            
        except Exception as e:
            raise ProcessingError(f"Failed to generate derivatives: {e}")
    
    async def _upload_derivatives(self, derivatives: Dict[int, bytes], 
                                profile_id: str, media_id: str) -> Dict[int, Dict[str, Any]]:
        """Upload derivatives to R2 storage"""
        upload_results = {}
        
        try:
            # Prepare upload objects for batch upload
            upload_objects = []
            
            for size, image_data in derivatives.items():
                # Generate content hash for immutable URL
                content_hash = hashlib.sha256(image_data).hexdigest()[:16]  # First 16 chars
                
                # Build R2 key (path)
                key = f"th/ig/{profile_id}/{media_id}/{size}/{content_hash}.webp"
                
                upload_objects.append({
                    'key': key,
                    'content': image_data,
                    'content_type': 'image/webp',
                    'cache_control': 'public, max-age=31536000, immutable',
                    'metadata': {
                        'profile-id': str(profile_id),
                        'media-id': media_id,
                        'size': str(size),
                        'generated-at': datetime.utcnow().isoformat()
                    }
                })
                
                # Prepare result data
                upload_results[size] = {
                    'path': f"/{key}",
                    'cdn_url': f"https://cdn.following.ae/{key}",
                    'content_hash': content_hash,
                    'file_size': len(image_data),
                    'dimensions': f"{size}x{size}",
                    'format': 'webp'
                }
            
            # Batch upload to R2
            batch_result = await self.r2_client.batch_upload(upload_objects)
            
            # Check for upload failures
            if batch_result['failed'] > 0:
                failed_keys = [error['key'] for error in batch_result['errors']]
                raise ProcessingError(f"Failed to upload derivatives: {failed_keys}")
            
            logger.info(f"📤 Uploaded {batch_result['successful']} derivatives to R2")
            return upload_results
            
        except Exception as e:
            raise ProcessingError(f"Failed to upload derivatives: {e}")
    
    def generate_content_hash(self, content: bytes) -> str:
        """Generate SHA256 hash for content"""
        return hashlib.sha256(content).hexdigest()
    
    async def validate_source_url(self, url: str) -> Dict[str, Any]:
        """Validate source URL without downloading full content"""
        try:
            # HEAD request to check URL validity
            response = await self.session.head(url, follow_redirects=True)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            content_length = int(response.headers.get('content-length', 0))
            
            return {
                'valid': True,
                'content_type': content_type,
                'content_length': content_length,
                'is_image': content_type.startswith('image/'),
                'size_ok': 1024 <= content_length <= 50 * 1024 * 1024,
                'final_url': str(response.url)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for image transcoder service"""
        health_status = {
            'status': 'healthy',
            'http_client_ready': False,
            'pil_available': False,
            'processing_stats': self.stats.copy(),
            'error': None
        }
        
        try:
            # Check HTTP client
            health_status['http_client_ready'] = not self.session.is_closed
            
            # Check PIL availability
            test_image = Image.new('RGB', (100, 100), color='red')
            test_buffer = io.BytesIO()
            test_image.save(test_buffer, format='WEBP', quality=85)
            health_status['pil_available'] = len(test_buffer.getvalue()) > 0
            
            # Overall status
            if not (health_status['http_client_ready'] and health_status['pil_available']):
                health_status['status'] = 'degraded'
                
        except Exception as e:
            health_status['status'] = 'unhealthy'
            health_status['error'] = str(e)
        
        return health_status
    
    async def close(self):
        """Clean up resources"""
        if self.session and not self.session.is_closed:
            await self.session.aclose()
        logger.info("🔒 Image Transcoder Service closed")
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics"""
        stats = self.stats.copy()
        
        # Calculate averages
        if stats['jobs_processed'] > 0:
            stats['avg_download_time_ms'] = stats['total_download_time_ms'] / stats['jobs_processed']
            stats['avg_processing_time_ms'] = stats['total_processing_time_ms'] / stats['jobs_processed']
            stats['avg_upload_time_ms'] = stats['total_upload_time_ms'] / stats['jobs_processed']
            stats['avg_bytes_per_job'] = stats['bytes_processed'] / stats['jobs_processed']
        else:
            stats['avg_download_time_ms'] = 0
            stats['avg_processing_time_ms'] = 0
            stats['avg_upload_time_ms'] = 0
            stats['avg_bytes_per_job'] = 0
        
        # Success rate
        total_jobs = stats['jobs_processed'] + stats['jobs_failed']
        stats['success_rate'] = (stats['jobs_processed'] / total_jobs * 100) if total_jobs > 0 else 0
        
        stats['last_updated'] = datetime.utcnow().isoformat()
        return stats


# Global transcoder service instance  
image_transcoder_service: Optional[ImageTranscoderService] = None