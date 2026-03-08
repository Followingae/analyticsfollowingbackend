"""
Location Detection Service

Detects creator's primary country using weighted analysis of multiple signals:
1. Biography Text Analysis (50% weight) - Direct creator statements
2. Content Keywords Analysis (20% weight) - Behavioral validation
3. Entity Extraction (10% weight) - Technical validation
4. Audience Top Country (20% weight) - Secondary signal
"""

import re
import unicodedata
from typing import Dict, List, Tuple, Optional
from collections import Counter
import logging

logger = logging.getLogger(__name__)

# Try to load spaCy, but don't fail if unavailable
try:
    import spacy
    _SPACY_AVAILABLE = True
except ImportError:
    _SPACY_AVAILABLE = False

# Try to load pycountry, but don't fail if unavailable
try:
    import pycountry
    _PYCOUNTRY_AVAILABLE = True
except ImportError:
    _PYCOUNTRY_AVAILABLE = False


class LocationDetectionService:

    def __init__(self):
        # Load spaCy model for entity extraction
        self.nlp = None
        if _SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not found, entity extraction will be disabled")

        # Country name mappings and aliases (English + Arabic + abbreviations)
        self.country_mappings = {
            # UAE
            "uae": "AE", "emirates": "AE", "dubai": "AE", "abu dhabi": "AE",
            "الامارات": "AE", "الإمارات": "AE", "دبي": "AE", "ابوظبي": "AE", "أبوظبي": "AE",
            "dxb": "AE",
            # USA
            "usa": "US", "america": "US", "united states": "US",
            "امريكا": "US", "أمريكا": "US",
            # UK
            "uk": "GB", "britain": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
            "بريطانيا": "GB", "لندن": "GB",
            # Saudi Arabia
            "ksa": "SA", "saudi": "SA", "saudi arabia": "SA",
            "السعودية": "SA", "المملكة": "SA",
            # Germany
            "germany": "DE", "deutschland": "DE", "المانيا": "DE", "ألمانيا": "DE",
            # France
            "france": "FR", "francia": "FR", "فرنسا": "FR",
            # Spain
            "spain": "ES", "españa": "ES", "اسبانيا": "ES", "إسبانيا": "ES",
            # Italy
            "italy": "IT", "italia": "IT", "ايطاليا": "IT", "إيطاليا": "IT",
            # Netherlands
            "netherlands": "NL", "holland": "NL", "هولندا": "NL",
            # Australia
            "australia": "AU", "aussie": "AU", "استراليا": "AU",
            # Canada
            "canada": "CA", "كندا": "CA",
            # India
            "india": "IN", "bharat": "IN", "الهند": "IN",
            # Japan
            "japan": "JP", "nippon": "JP", "اليابان": "JP",
            # China
            "china": "CN", "prc": "CN", "الصين": "CN",
            # Russia
            "russia": "RU", "russian federation": "RU", "روسيا": "RU",
            # Brazil
            "brazil": "BR", "brasil": "BR", "البرازيل": "BR",
            # Mexico
            "mexico": "MX", "méxico": "MX", "المكسيك": "MX",
            # Turkey
            "turkey": "TR", "türkiye": "TR", "تركيا": "TR",
            # Egypt
            "egypt": "EG", "مصر": "EG",
            # Lebanon
            "lebanon": "LB", "لبنان": "LB",
            # Jordan
            "jordan": "JO", "الأردن": "JO", "الاردن": "JO",
            # Kuwait
            "kuwait": "KW", "الكويت": "KW",
            # Qatar
            "qatar": "QA", "قطر": "QA",
            # Bahrain
            "bahrain": "BH", "البحرين": "BH",
            # Oman
            "oman": "OM", "عمان": "OM", "عُمان": "OM",
            # Iraq
            "iraq": "IQ", "العراق": "IQ",
            # Morocco
            "morocco": "MA", "المغرب": "MA",
            # Tunisia
            "tunisia": "TN", "تونس": "TN",
            # Algeria
            "algeria": "DZ", "الجزائر": "DZ",
            # Pakistan
            "pakistan": "PK", "باكستان": "PK",
            # South Korea
            "south korea": "KR", "korea": "KR",
            # Singapore
            "singapore": "SG",
            # Thailand
            "thailand": "TH", "bangkok": "TH",
            # Indonesia
            "indonesia": "ID",
            # Malaysia
            "malaysia": "MY",
            # Philippines
            "philippines": "PH",
            # Portugal
            "portugal": "PT",
            # Sweden
            "sweden": "SE",
            # Norway
            "norway": "NO",
            # Denmark
            "denmark": "DK",
            # Switzerland
            "switzerland": "CH", "suisse": "CH",
            # Austria
            "austria": "AT",
            # Belgium
            "belgium": "BE",
            # Ireland
            "ireland": "IE",
            # Poland
            "poland": "PL",
            # Greece
            "greece": "GR",
        }

        # City to country mappings (English + Arabic + abbreviations)
        self.city_mappings = {
            # UAE cities
            "dubai": "AE", "abu dhabi": "AE", "sharjah": "AE", "ajman": "AE",
            "ras al khaimah": "AE", "fujairah": "AE", "al ain": "AE",
            "دبي": "AE", "ابوظبي": "AE", "أبوظبي": "AE", "الشارقة": "AE",
            "عجمان": "AE", "العين": "AE", "رأس الخيمة": "AE", "الفجيرة": "AE",
            "jbr": "AE", "dxb": "AE", "jlt": "AE", "difc": "AE",
            # Saudi cities
            "riyadh": "SA", "jeddah": "SA", "mecca": "SA", "medina": "SA", "dammam": "SA",
            "الرياض": "SA", "جدة": "SA", "مكة": "SA", "المدينة": "SA", "الدمام": "SA",
            # Kuwait
            "kuwait city": "KW", "مدينة الكويت": "KW",
            # Qatar
            "doha": "QA", "الدوحة": "QA",
            # Bahrain
            "manama": "BH", "المنامة": "BH",
            # Egypt
            "cairo": "EG", "alexandria": "EG", "القاهرة": "EG", "الاسكندرية": "EG",
            # Lebanon
            "beirut": "LB", "بيروت": "LB",
            # Jordan
            "amman": "JO", "عمّان": "JO",
            # Iraq
            "baghdad": "IQ", "erbil": "IQ", "بغداد": "IQ", "اربيل": "IQ",
            # Morocco
            "casablanca": "MA", "marrakech": "MA", "الدار البيضاء": "MA",
            # US cities
            "new york": "US", "los angeles": "US", "chicago": "US", "miami": "US",
            "san francisco": "US", "boston": "US", "seattle": "US", "las vegas": "US",
            "houston": "US", "dallas": "US", "atlanta": "US", "nyc": "US", "la": "US",
            # UK cities
            "london": "GB", "manchester": "GB", "birmingham": "GB", "glasgow": "GB",
            "edinburgh": "GB", "liverpool": "GB", "bristol": "GB",
            # European cities
            "paris": "FR", "berlin": "DE", "madrid": "ES", "barcelona": "ES",
            "rome": "IT", "milan": "IT", "amsterdam": "NL", "brussels": "BE",
            "munich": "DE", "vienna": "AT", "zurich": "CH", "geneva": "CH",
            "lisbon": "PT", "dublin": "IE", "copenhagen": "DK", "stockholm": "SE",
            "oslo": "NO", "helsinki": "FI", "prague": "CZ", "warsaw": "PL",
            "athens": "GR", "istanbul": "TR",
            # Asia-Pacific cities
            "tokyo": "JP", "osaka": "JP", "seoul": "KR", "beijing": "CN",
            "shanghai": "CN", "hong kong": "HK", "singapore": "SG",
            "bangkok": "TH", "mumbai": "IN", "delhi": "IN", "bangalore": "IN",
            "jakarta": "ID", "kuala lumpur": "MY", "manila": "PH",
            # Other
            "sydney": "AU", "melbourne": "AU", "toronto": "CA", "vancouver": "CA",
            "moscow": "RU", "são paulo": "BR", "mexico city": "MX",
        }

        # Flag emoji to country code mapping
        self.flag_emoji_mappings = {
            "🇦🇪": "AE", "🇺🇸": "US", "🇬🇧": "GB", "🇸🇦": "SA", "🇰🇼": "KW",
            "🇶🇦": "QA", "🇧🇭": "BH", "🇴🇲": "OM", "🇮🇶": "IQ", "🇯🇴": "JO",
            "🇱🇧": "LB", "🇪🇬": "EG", "🇲🇦": "MA", "🇹🇳": "TN", "🇩🇿": "DZ",
            "🇹🇷": "TR", "🇩🇪": "DE", "🇫🇷": "FR", "🇪🇸": "ES", "🇮🇹": "IT",
            "🇳🇱": "NL", "🇧🇪": "BE", "🇦🇹": "AT", "🇨🇭": "CH", "🇸🇪": "SE",
            "🇳🇴": "NO", "🇩🇰": "DK", "🇮🇪": "IE", "🇵🇹": "PT", "🇬🇷": "GR",
            "🇵🇱": "PL", "🇨🇿": "CZ", "🇷🇺": "RU", "🇺🇦": "UA",
            "🇮🇳": "IN", "🇵🇰": "PK", "🇯🇵": "JP", "🇰🇷": "KR", "🇨🇳": "CN",
            "🇭🇰": "HK", "🇸🇬": "SG", "🇹🇭": "TH", "🇮🇩": "ID", "🇲🇾": "MY",
            "🇵🇭": "PH", "🇦🇺": "AU", "🇳🇿": "NZ", "🇨🇦": "CA", "🇧🇷": "BR",
            "🇲🇽": "MX", "🇦🇷": "AR", "🇨🇴": "CO",
        }

    def detect_country(self, profile_data: dict) -> Dict:
        """
        Detect creator's primary country using weighted analysis

        Returns:
        {
            "country_code": "AE",
            "confidence": 0.85,
            "signals": { ... }
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

        # Check flag emojis first (high confidence — deliberate choice by creator)
        for emoji, country_code in self.flag_emoji_mappings.items():
            if emoji in biography:  # Check original (not lowered) for emoji
                countries_found[country_code] = max(
                    countries_found.get(country_code, 0),
                    0.95  # Flag emojis are very strong signals
                )

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

        # Look for location indicators
        location_indicators = [
            "📍", "based in", "from", "live in", "living in",
            "located in", "born in", "raised in", "hometown",
        ]
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

        # Also check flag emojis in post content (use original case text)
        all_text_original = " ".join(post.get("caption", "") for post in posts if post.get("caption"))
        for emoji, country_code in self.flag_emoji_mappings.items():
            if emoji in all_text_original:
                # Flag emoji in posts is a moderate signal
                pass  # Will be caught by location_counts below via country_mappings

        # Count location mentions
        location_counts = {}
        for location, country_code in {**self.country_mappings, **self.city_mappings}.items():
            # Use word boundary check for short terms to avoid false positives
            if len(location) <= 2:
                # Skip very short terms in content analysis (too many false positives)
                continue
            count = all_text.count(location)
            if count > 0:
                if country_code not in location_counts:
                    location_counts[country_code] = 0
                location_counts[country_code] += count

        # Also check flag emojis in content
        for emoji, country_code in self.flag_emoji_mappings.items():
            if emoji in all_text_original:
                if country_code not in location_counts:
                    location_counts[country_code] = 0
                location_counts[country_code] += all_text_original.count(emoji) * 2  # Flag emojis weighted higher

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

        # Normalize Unicode before NER
        normalized_bio = unicodedata.normalize('NFKD', biography)
        doc = self.nlp(normalized_bio)
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
        if not _PYCOUNTRY_AVAILABLE:
            return country_code
        try:
            country = pycountry.countries.get(alpha_2=country_code)
            return country.name if country else country_code
        except:
            return country_code
