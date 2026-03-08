"""
CLIP-based Visual Content Analyzer
Uses OpenAI's CLIP model (openai/clip-vit-base-patch32) - MIT license, completely free, self-hosted.
Zero-shot image classification for brand detection, scene classification, content type detection.
"""
import asyncio
import logging
import threading
from typing import Dict, List, Any, Optional
from io import BytesIO
import numpy as np

logger = logging.getLogger(__name__)

# Curated brand list for zero-shot detection (top Instagram influencer brands)
BRAND_NAMES = [
    "Nike", "Adidas", "Gucci", "Louis Vuitton", "Chanel", "Dior", "Prada",
    "Zara", "H&M", "Apple", "Samsung", "Coca-Cola", "Starbucks", "McDonald's",
    "BMW", "Mercedes-Benz", "Audi", "Sephora", "MAC Cosmetics", "Fenty Beauty",
    "Glossier", "Gymshark", "Lululemon", "Under Armour", "New Balance", "Puma",
    "Ray-Ban", "Rolex", "Versace", "Balenciaga", "Supreme", "Calvin Klein",
    "Tommy Hilfiger", "Ralph Lauren", "Burberry", "Michael Kors", "Coach",
    "Daniel Wellington", "Sony", "Canon", "GoPro", "Red Bull", "Monster Energy",
    "Netflix", "Spotify", "Amazon", "Google", "Tesla", "Porsche", "Ferrari",
]

SCENE_PROMPTS = {
    "outdoor_nature": "outdoor nature scenery with trees or mountains",
    "beach": "beach or seaside with sand and water",
    "city_urban": "city street or urban environment with buildings",
    "gym_fitness": "gym or fitness workout environment",
    "restaurant_food": "restaurant or cafe with food and drinks",
    "home_indoor": "indoor home or apartment setting",
    "studio": "professional photo studio with controlled lighting",
    "office": "office or workspace environment",
    "travel": "travel destination or tourist attraction",
    "event_party": "event, party, or social gathering",
    "shopping": "shopping mall or retail store",
    "pool_resort": "swimming pool or luxury resort",
    "sports": "sports field or athletic activity",
}

CONTENT_TYPE_PROMPTS = {
    "selfie": "a selfie or close-up portrait of a person",
    "group_photo": "a group photo with multiple people together",
    "product": "a product display or flat lay arrangement",
    "food": "food, meal, or drink photography",
    "fashion": "fashion outfit or clothing display",
    "fitness": "workout, exercise, or gym activity",
    "landscape": "landscape, scenery, or nature photography",
    "pet": "pet or animal photograph",
    "lifestyle": "lifestyle or daily activity moment",
    "art": "artistic or creative photography",
    "car": "car, motorcycle, or vehicle photograph",
    "tech": "technology, gadget, or electronics",
}

SCENE_LABELS = {
    "outdoor_nature": "Outdoor / Nature",
    "beach": "Beach",
    "city_urban": "City / Urban",
    "gym_fitness": "Gym / Fitness",
    "restaurant_food": "Restaurant / Food",
    "home_indoor": "Home / Indoor",
    "studio": "Studio",
    "office": "Office",
    "travel": "Travel",
    "event_party": "Event / Party",
    "shopping": "Shopping",
    "pool_resort": "Pool / Resort",
    "sports": "Sports",
}

CONTENT_TYPE_LABELS = {
    "selfie": "Selfie",
    "group_photo": "Group Photo",
    "product": "Product / Flat Lay",
    "food": "Food & Drink",
    "fashion": "Fashion / OOTD",
    "fitness": "Fitness",
    "landscape": "Landscape",
    "pet": "Pet / Animal",
    "lifestyle": "Lifestyle",
    "art": "Art / Creative",
    "car": "Automotive",
    "tech": "Tech / Gadgets",
}


class CLIPVisualAnalyzer:
    """
    CLIP-based visual content analysis. Singleton with lazy model loading.
    Model: openai/clip-vit-base-patch32 (MIT license, ~605MB, self-hosted).
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_done = False
        return cls._instance

    def __init__(self):
        if self._init_done:
            return
        self._init_done = True
        self._model = None
        self._processor = None
        self._text_embeds: Dict[str, Any] = {}
        self._model_ready = False
        self._model_lock = threading.Lock()

    def _ensure_model(self):
        """Lazy-load CLIP model on first use (not at application startup)"""
        if self._model_ready:
            return
        with self._model_lock:
            if self._model_ready:
                return
            import torch
            from transformers import CLIPModel, CLIPProcessor
            import os

            cache_dir = os.getenv('AI_MODELS_CACHE_DIR', './ai_models')
            logger.info("[CLIP] Loading openai/clip-vit-base-patch32 ...")
            self._model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32", cache_dir=cache_dir)
            self._processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32", cache_dir=cache_dir)
            self._model.eval()
            self._precompute_text_embeddings()
            self._model_ready = True
            logger.info("[CLIP] Model loaded and text embeddings pre-computed")

    def _precompute_text_embeddings(self):
        """Pre-compute text embeddings for all prompts (called once at model load)"""
        import torch

        def _embed_texts(texts: List[str]):
            inputs = self._processor(text=texts, return_tensors="pt", padding=True, truncation=True)
            with torch.no_grad():
                embeds = self._model.get_text_features(**inputs)
                return embeds / embeds.norm(dim=-1, keepdim=True)

        # Brand prompts + "no brand" control
        brand_texts = [f"a photo featuring {b} products or branding" for b in BRAND_NAMES]
        brand_texts.append("a photo without any recognizable brand or logo")
        self._text_embeds['brands'] = _embed_texts(brand_texts)

        self._text_embeds['scenes'] = _embed_texts(list(SCENE_PROMPTS.values()))
        self._text_embeds['content'] = _embed_texts(list(CONTENT_TYPE_PROMPTS.values()))

        quality_texts = [
            "a professionally shot photograph with excellent lighting and composition",
            "a casual phone snapshot or amateur photograph",
        ]
        self._text_embeds['quality'] = _embed_texts(quality_texts)

    # ── Public API ────────────────────────────────────────────────────────

    async def analyze_visual_content(self, posts_data: List[dict]) -> Dict[str, Any]:
        """Analyze post images using CLIP zero-shot classification"""
        try:
            self._ensure_model()
        except Exception as e:
            logger.error(f"[CLIP] Model load failed: {e}")
            return self._empty(posts_data)

        import torch

        images = await self._download_images(posts_data[:12])
        if not images:
            logger.warning("[CLIP] No images downloaded")
            return self._empty(posts_data)

        logger.info(f"[CLIP] Processing {len(images)} images ...")

        brand_scores: Dict[str, Dict] = {}
        scene_votes: Dict[str, float] = {k: 0.0 for k in SCENE_PROMPTS}
        content_votes: Dict[str, int] = {k: 0 for k in CONTENT_TYPE_PROMPTS}
        quality_scores: List[float] = []
        img_embeds: List[Any] = []

        for img in images:
            try:
                inputs = self._processor(images=img, return_tensors="pt")
                with torch.no_grad():
                    embed = self._model.get_image_features(**inputs)
                    embed = embed / embed.norm(dim=-1, keepdim=True)
                img_embeds.append(embed)

                # Brand detection
                sims = (embed @ self._text_embeds['brands'].T).squeeze()
                probs = sims.softmax(dim=0).cpu().numpy()
                for idx, brand in enumerate(BRAND_NAMES):
                    score = float(probs[idx])
                    if score > 0.03:
                        if brand not in brand_scores:
                            brand_scores[brand] = {'total': 0.0, 'count': 0}
                        brand_scores[brand]['total'] += score
                        brand_scores[brand]['count'] += 1

                # Scene
                sims = (embed @ self._text_embeds['scenes'].T).squeeze()
                probs = sims.softmax(dim=0).cpu().numpy()
                best = int(np.argmax(probs))
                scene_key = list(SCENE_PROMPTS.keys())[best]
                scene_votes[scene_key] += 1

                # Content type
                sims = (embed @ self._text_embeds['content'].T).squeeze()
                probs = sims.softmax(dim=0).cpu().numpy()
                best = int(np.argmax(probs))
                ct_key = list(CONTENT_TYPE_PROMPTS.keys())[best]
                content_votes[ct_key] += 1

                # Quality
                sims = (embed @ self._text_embeds['quality'].T).squeeze()
                probs = sims.softmax(dim=0).cpu().numpy()
                quality_scores.append(float(probs[0]))

            except Exception as e:
                logger.warning(f"[CLIP] Image analysis failed: {e}")

        n = len(images)

        # ── Aggregate brands ──────────────────────────────────────────
        brands_detected = []
        for brand, data in sorted(brand_scores.items(), key=lambda x: x[1]['total'], reverse=True):
            avg = data['total'] / data['count']
            if avg > 0.04 and data['count'] >= 1:
                brands_detected.append({
                    'brand': brand,
                    'confidence': round(avg, 3),
                    'post_count': data['count'],
                })
        brands_detected = brands_detected[:10]

        # ── Scene distribution (percentages) ──────────────────────────
        total_votes = sum(scene_votes.values()) or 1
        scene_distribution = {}
        for key, count in scene_votes.items():
            pct = round((count / total_votes) * 100, 1)
            if pct > 0:
                scene_distribution[key] = pct

        # ── Content types (counts) ────────────────────────────────────
        content_types = {k: v for k, v in content_votes.items() if v > 0}

        # ── Visual consistency (avg pairwise cosine similarity) ───────
        visual_consistency = None
        if len(img_embeds) >= 2:
            all_e = torch.cat(img_embeds, dim=0)
            sim = (all_e @ all_e.T).cpu().numpy()
            m = sim.shape[0]
            off_diag = sim.sum() - np.trace(sim)
            visual_consistency = round(float(off_diag / (m * (m - 1))), 3)

        # ── Production quality ────────────────────────────────────────
        avg_pro = float(np.mean(quality_scores)) if quality_scores else 0.5
        if avg_pro >= 0.65:
            production_quality = "professional"
        elif avg_pro >= 0.45:
            production_quality = "mixed"
        else:
            production_quality = "casual"

        result = {
            'visual_analysis': {
                'total_posts': len(posts_data),
                'images_processed': n,
                'processing_success_rate': round(n / max(len(posts_data), 1), 2),
                'analysis_method': 'clip',
            },
            'brands_detected': brands_detected,
            'scene_distribution': scene_distribution,
            'content_types': content_types,
            'visual_consistency': visual_consistency,
            'production_quality': production_quality,
            'professional_score': round(avg_pro * 100, 1),
            # Backward-compat keys (consumed by existing response builder)
            'aesthetic_score': round((visual_consistency or 0.5) * 100, 1),
            'professional_quality_score': round(avg_pro * 100, 1),
            'dominant_colors': [],
            'brand_logo_detected': [b['brand'] for b in brands_detected[:5]],
            'face_analysis': {'faces_detected': 0, 'unique_faces': 0, 'celebrities': [], 'emotions': []},
            'image_quality_metrics': {
                'average_quality': round(avg_pro * 100, 1),
                'quality_consistency': visual_consistency,
            },
        }

        logger.info(
            f"[CLIP] Done: {n} images, {len(brands_detected)} brands, "
            f"{len(scene_distribution)} scenes, quality={production_quality}"
        )
        return result

    # ── Image downloading ─────────────────────────────────────────────

    async def _download_images(self, posts_data: List[dict]) -> list:
        """Download post images in parallel using aiohttp"""
        from PIL import Image
        import aiohttp

        async def _one(post: dict):
            url = (
                post.get('cdn_thumbnail_url')
                or post.get('display_url')
                or post.get('thumbnail_url')
            )
            if not url:
                return None
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            return None
                        data = await resp.read()
                        if len(data) > 10 * 1024 * 1024:
                            return None
                        return Image.open(BytesIO(data)).convert('RGB')
            except Exception as e:
                logger.debug(f"[CLIP] Download failed {url[:60]}: {e}")
                return None

        results = await asyncio.gather(*[_one(p) for p in posts_data], return_exceptions=True)
        return [r for r in results if r is not None and not isinstance(r, Exception)]

    # ── Empty fallback ────────────────────────────────────────────────

    def _empty(self, posts_data: List[dict]) -> Dict[str, Any]:
        return {
            'visual_analysis': {
                'total_posts': len(posts_data),
                'images_processed': 0,
                'processing_success_rate': 0.0,
                'analysis_method': 'unavailable',
            },
            'brands_detected': [],
            'scene_distribution': {},
            'content_types': {},
            'visual_consistency': None,
            'production_quality': None,
            'professional_score': None,
            'aesthetic_score': None,
            'professional_quality_score': None,
            'dominant_colors': [],
            'brand_logo_detected': [],
            'face_analysis': {'faces_detected': 0, 'unique_faces': 0, 'celebrities': [], 'emotions': []},
            'image_quality_metrics': {},
        }
