"""
Location Detection Service

Detects creator's primary country using weighted analysis of multiple signals:
1. Biography Text Analysis (50% weight) - Direct creator statements
2. Content Keywords Analysis (20% weight) - Behavioral validation
3. Entity Extraction (10% weight) - Technical validation
4. Audience Top Country (20% weight) - Secondary signal
"""

import re
import spacy
import unicodedata
from typing import Dict, List, Tuple, Optional
from collections import Counter
import pycountry
import logging

logger = logging.getLogger(__name__)

class LocationDetectionService:

    def __init__(self):
        # Load spaCy model for entity extraction
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model not found, entity extraction will be disabled")
            self.nlp = None

        # Country name mappings and aliases
        self.country_mappings = {
            # Common variations and aliases
            "uae": "AE", "emirates": "AE", "dubai": "AE", "abu dhabi": "AE",
            "usa": "US", "america": "US", "united states": "US",
            "uk": "GB", "britain": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
            "ksa": "SA", "saudi": "SA", "saudi arabia": "SA",
            "germany": "DE", "deutschland": "DE",
            "france": "FR", "francia": "FR",
            "spain": "ES", "españa": "ES",
            "italy": "IT", "italia": "IT",
            "netherlands": "NL", "holland": "NL",
            "australia": "AU", "aussie": "AU",
            "canada": "CA",
            "india": "IN", "bharat": "IN",
            "japan": "JP", "nippon": "JP",
            "china": "CN", "prc": "CN",
            "russia": "RU", "russian federation": "RU",
            "brazil": "BR", "brasil": "BR",
            "mexico": "MX", "méxico": "MX",
            "turkey": "TR", "türkiye": "TR",
            "egypt": "EG", "مصر": "EG",
            "lebanon": "LB", "لبنان": "LB",
            "jordan": "JO", "الأردن": "JO",
            "kuwait": "KW", "الكويت": "KW",
            "qatar": "QA", "قطر": "QA",
            "bahrain": "BH", "البحرين": "BH",
            "oman": "OM", "عمان": "OM",
        }

        # City to country mappings
        self.city_mappings = {
            # UAE cities
            "dubai": "AE", "abu dhabi": "AE", "sharjah": "AE", "ajman": "AE",
            # US cities
            "new york": "US", "los angeles": "US", "chicago": "US", "miami": "US",
            "san francisco": "US", "boston": "US", "seattle": "US", "las vegas": "US",
            # UK cities
            "london": "GB", "manchester": "GB", "birmingham": "GB", "glasgow": "GB",
            "edinburgh": "GB", "liverpool": "GB", "bristol": "GB",
            # Other major cities
            "paris": "FR", "berlin": "DE", "madrid": "ES", "rome": "IT",
            "amsterdam": "NL", "sydney": "AU", "melbourne": "AU", "toronto": "CA",
            "vancouver": "CA", "mumbai": "IN", "delhi": "IN", "tokyo": "JP",
            "beijing": "CN", "shanghai": "CN", "moscow": "RU", "istanbul": "TR",
            "cairo": "EG", "beirut": "LB", "amman": "JO", "riyadh": "SA",
            "jeddah": "SA", "doha": "QA", "kuwait city": "KW",
        }

    def detect_country(self, profile_data: dict) -> Dict:
        """
        Detect creator's primary country using weighted analysis

        Returns:
        {
            "country_code": "AE",
            "confidence": 0.85,
            "signals": {
                "biography": {"score": 0.45, "countries": {"AE": 0.9}},
                "content": {"score": 0.20, "countries": {"AE": 1.0}},
                "entities": {"score": 0.10, "countries": {"AE": 1.0}},
                "audience": {"score": 0.02, "countries": {"US": 0.1}}
            }
        }
        """

        signals = {
            "biography": self._analyze_biography(profile_data.get("biography", "")),
            "content": self._analyze_content_keywords(profile_data.get("posts", [])),
            "entities": self._extract_location_entities(profile_data.get("biography", "")),
            "audience": self._analyze_audience_country(profile_data.get("audience_top_countries", []))
        }

        # Calculate weighted scores
        weights = {
            "biography": 0.50,    # 50% - Direct creator statements
            "content": 0.20,      # 20% - Behavioral validation
            "entities": 0.10,     # 10% - Technical validation
            "audience": 0.20      # 20% - Secondary signal
        }

        country_scores = {}

        for signal_type, signal_data in signals.items():
            weight = weights[signal_type]
            signal_score = signal_data["score"]

            for country, country_confidence in signal_data["countries"].items():
                if country not in country_scores:
                    country_scores[country] = 0
                country_scores[country] += weight * signal_score * country_confidence

        # Find top country
        if not country_scores:
            return {
                "country_code": None,
                "confidence": 0.0,
                "signals": signals
            }

        top_country = max(country_scores, key=country_scores.get)
        top_score = country_scores[top_country]

        return {
            "country_code": top_country,
            "confidence": min(top_score, 1.0),  # Cap at 1.0
            "signals": signals
        }

    def _analyze_biography(self, biography: str) -> Dict:
        """Analyze biography text for location indicators"""
        if not biography:
            return {"score": 0.0, "countries": {}}

        # Normalize Unicode characters to handle stylized text (𝐃𝐮𝐛𝐚𝐢 -> Dubai)
        normalized_bio = unicodedata.normalize('NFKD', biography)
        bio_lower = normalized_bio.lower()
        countries_found = {}

        # Look for country names and aliases
        for location, country_code in self.country_mappings.items():
            if location in bio_lower:
                # Higher confidence for more specific matches
                confidence = 0.9 if len(location) > 3 else 0.7
                countries_found[country_code] = max(
                    countries_found.get(country_code, 0),
                    confidence
                )

        # Look for city names
        for city, country_code in self.city_mappings.items():
            if city in bio_lower:
                confidence = 0.8  # Cities are good indicators
                countries_found[country_code] = max(
                    countries_found.get(country_code, 0),
                    confidence
                )

        # Look for location emojis and indicators
        location_indicators = ["📍", "🇦🇪", "🇺🇸", "🇬🇧", "🇸🇦", "based in", "from", "live in"]
        has_location_indicator = any(indicator in bio_lower for indicator in location_indicators)

        if countries_found and has_location_indicator:
            # Boost confidence if explicit location indicators present
            for country in countries_found:
                countries_found[country] = min(countries_found[country] + 0.1, 1.0)

        score = 1.0 if countries_found else 0.0

        return {
            "score": score,
            "countries": countries_found
        }

    def _analyze_content_keywords(self, posts: List[dict]) -> Dict:
        """Analyze post content for location-related keywords"""
        if not posts:
            return {"score": 0.0, "countries": {}}

        # Collect all captions and analyze keywords
        all_text = ""
        for post in posts:
            caption = post.get("caption", "")
            if caption:
                all_text += " " + caption.lower()

        if not all_text.strip():
            return {"score": 0.0, "countries": {}}

        # Count location mentions
        location_counts = {}
        for location, country_code in {**self.country_mappings, **self.city_mappings}.items():
            count = all_text.count(location)
            if count > 0:
                if country_code not in location_counts:
                    location_counts[country_code] = 0
                location_counts[country_code] += count

        if not location_counts:
            return {"score": 0.0, "countries": {}}

        # Calculate confidence based on frequency
        total_mentions = sum(location_counts.values())
        countries_found = {}

        for country, count in location_counts.items():
            confidence = min(count / max(total_mentions, 5), 1.0)  # Normalize to reasonable scale
            countries_found[country] = confidence

        return {
            "score": 1.0,
            "countries": countries_found
        }

    def _extract_location_entities(self, biography: str) -> Dict:
        """Extract location entities using spaCy NER"""
        if not biography or not self.nlp:
            return {"score": 0.0, "countries": {}}

        doc = self.nlp(biography)
        locations = []

        for ent in doc.ents:
            if ent.label_ in ["GPE", "LOC"]:  # Geopolitical entities, locations
                locations.append(ent.text.lower())

        if not locations:
            return {"score": 0.0, "countries": {}}

        # Map entities to countries
        countries_found = {}
        for location in locations:
            # Check direct mappings
            for mapped_location, country_code in {**self.country_mappings, **self.city_mappings}.items():
                if mapped_location in location or location in mapped_location:
                    countries_found[country_code] = 1.0
                    break

        score = 1.0 if countries_found else 0.0

        return {
            "score": score,
            "countries": countries_found
        }

    def _analyze_audience_country(self, audience_countries: List[dict]) -> Dict:
        """Analyze audience top countries as secondary signal"""
        if not audience_countries:
            return {"score": 0.0, "countries": {}}

        # Take top audience country with low confidence
        # (audience location ≠ creator location in many cases)
        top_country = audience_countries[0] if audience_countries else None

        if not top_country:
            return {"score": 0.0, "countries": {}}

        country_code = top_country.get("country_code", "").upper()
        percentage = top_country.get("percentage", 0)

        # Low confidence since audience ≠ creator location
        confidence = min(percentage / 100, 0.3)  # Max 30% confidence

        return {
            "score": 1.0,
            "countries": {country_code: confidence} if country_code else {}
        }

    def get_country_name(self, country_code: str) -> str:
        """Get full country name from ISO code"""
        try:
            country = pycountry.countries.get(alpha_2=country_code)
            return country.name if country else country_code
        except:
            return country_code