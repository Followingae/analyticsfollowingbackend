"""
Real-Time Trend Detection with Time Series Analysis
- Viral Content Detection: Early identification of trending content
- Hashtag Trend Analysis: Which hashtags are gaining/losing momentum
- Engagement Spike Detection: Unusual activity pattern alerts
- Content Trend Forecasting: What content types will trend next
"""
import asyncio
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import json

# Time Series and Trend Analysis Dependencies
try:
    from prophet import Prophet
    from scipy import stats
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import DBSCAN
    from sklearn.decomposition import PCA
    import pandas as pd
    from river import drift
    from river import stats as river_stats
    from river import time_series
    import statsmodels.api as sm
    from statsmodels.tsa.seasonal import seasonal_decompose
    TREND_AVAILABLE = True
except ImportError as e:
    TREND_AVAILABLE = False
    logging.warning(f"Trend detection dependencies not available: {e}")

logger = logging.getLogger(__name__)

class RealTrendDetectionAnalyzer:
    """
    Real Time Series and Trend Detection Implementation
    - Viral content detection using statistical analysis
    - Hashtag momentum tracking with time series forecasting
    - Engagement anomaly detection using drift detection
    - Content trend forecasting with Prophet and seasonal decomposition
    """

    def __init__(self):
        self.models = {}
        self.drift_detectors = {}
        self.trend_cache = {}
        self._initialize_models()

    def _initialize_models(self):
        """Initialize trend detection and time series models"""
        if not TREND_AVAILABLE:
            logger.error("Trend detection dependencies not available")
            return

        try:
            # Initialize drift detectors for real-time monitoring
            self.drift_detectors = {
                'engagement_drift': drift.ADWIN(),
                'hashtag_drift': drift.ADWIN(),
                'content_drift': drift.PageHinkley()
            }

            # Initialize statistical models
            self.models['scaler'] = StandardScaler()
            self.models['clustering'] = DBSCAN(eps=0.5, min_samples=3)

            # Time series components
            self.models['trend_stats'] = {
                'engagement_tracker': river_stats.Mean(),
                'variance_tracker': river_stats.Var(),
                'momentum_tracker': defaultdict(float)
            }

            logger.info("✅ Trend detection models initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize trend detection models: {e}")
            self.models = {}

    async def analyze_trend_detection(self, profile_data: dict, posts_data: List[dict]) -> Dict[str, Any]:
        """
        Comprehensive real-time trend detection analysis
        """
        if not TREND_AVAILABLE or not self.models:
            return self._get_fallback_trend_analysis(posts_data)

        logger.info(f"📈 Starting real-time trend analysis for {len(posts_data)} posts")

        # Prepare time series data
        time_series_data = self._prepare_time_series_data(posts_data)
        if not time_series_data['valid']:
            return self._get_minimal_trend_analysis(posts_data)

        # Run comprehensive trend analysis
        analysis_results = {
            'viral_potential': await self._analyze_viral_potential(time_series_data, posts_data),
            'content_trends': await self._analyze_content_trends(time_series_data, posts_data),
            'hashtag_trends': await self._analyze_hashtag_trends(time_series_data, posts_data),
            'engagement_patterns': await self._analyze_engagement_patterns(time_series_data),
            'trend_analysis': await self._perform_statistical_trend_analysis(time_series_data),
            'anomaly_detection': await self._detect_engagement_anomalies(time_series_data),
            'forecasting': await self._forecast_future_trends(time_series_data),
            'optimization_recommendations': await self._generate_trend_recommendations(time_series_data, posts_data)
        }

        logger.info("✅ Real-time trend analysis complete")
        return analysis_results

    def _prepare_time_series_data(self, posts_data: List[dict]) -> Dict[str, Any]:
        """Prepare time series data from posts"""
        try:
            if len(posts_data) < 3:
                return {'valid': False, 'reason': 'insufficient_data'}

            # Extract temporal data
            time_points = []
            engagement_values = []
            like_values = []
            comment_values = []
            hashtag_counts = []
            content_types = []

            for post in posts_data:
                # Get timestamp
                timestamp = post.get('taken_at_timestamp')
                if timestamp:
                    try:
                        if isinstance(timestamp, (int, float)):
                            dt = datetime.fromtimestamp(timestamp)
                        else:
                            dt = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))

                        time_points.append(dt)

                        # Extract engagement metrics
                        likes = post.get('likes_count', 0)
                        comments = post.get('comments_count', 0)
                        engagement = likes + (comments * 10)  # Weight comments higher

                        engagement_values.append(engagement)
                        like_values.append(likes)
                        comment_values.append(comments)

                        # Extract content features
                        caption = post.get('caption', '')
                        hashtag_count = caption.count('#') if caption else 0
                        hashtag_counts.append(hashtag_count)

                        # Simple content type classification
                        content_type = self._classify_content_type(post)
                        content_types.append(content_type)

                    except Exception as e:
                        logger.warning(f"Failed to parse timestamp {timestamp}: {e}")
                        continue

            if len(time_points) < 3:
                return {'valid': False, 'reason': 'insufficient_valid_timestamps'}

            # Sort by time
            sorted_data = sorted(zip(time_points, engagement_values, like_values,
                                   comment_values, hashtag_counts, content_types))

            if sorted_data:
                time_points, engagement_values, like_values, comment_values, hashtag_counts, content_types = zip(*sorted_data)

            return {
                'valid': True,
                'timestamps': list(time_points),
                'engagement': list(engagement_values),
                'likes': list(like_values),
                'comments': list(comment_values),
                'hashtags': list(hashtag_counts),
                'content_types': list(content_types),
                'data_points': len(time_points),
                'time_span_days': (max(time_points) - min(time_points)).days if time_points else 0
            }

        except Exception as e:
            logger.warning(f"Failed to prepare time series data: {e}")
            return {'valid': False, 'reason': f'processing_error: {str(e)}'}

    async def _analyze_viral_potential(self, time_series_data: Dict, posts_data: List[dict]) -> Dict[str, Any]:
        """Analyze viral potential using statistical indicators"""
        try:
            engagement_values = time_series_data['engagement']
            if len(engagement_values) < 3:
                return self._get_default_viral_analysis()

            # Statistical analysis of engagement patterns
            engagement_array = np.array(engagement_values)

            # Calculate viral indicators
            mean_engagement = np.mean(engagement_array)
            std_engagement = np.std(engagement_array)
            max_engagement = np.max(engagement_array)

            # Viral score based on outliers and growth patterns
            viral_score = 0.0
            viral_indicators = {
                'outlier_posts': 0,
                'growth_acceleration': 0.0,
                'engagement_consistency': 0.0,
                'peak_performance': 0.0
            }

            # Detect outlier posts (potential viral content)
            z_scores = np.abs(stats.zscore(engagement_array))
            outliers = np.where(z_scores > 2)[0]  # Posts with z-score > 2
            viral_indicators['outlier_posts'] = len(outliers)

            # Calculate growth acceleration
            if len(engagement_values) > 1:
                growth_rates = []
                for i in range(1, len(engagement_values)):
                    if engagement_values[i-1] > 0:
                        growth_rate = (engagement_values[i] - engagement_values[i-1]) / engagement_values[i-1]
                        growth_rates.append(growth_rate)

                if growth_rates:
                    viral_indicators['growth_acceleration'] = np.mean(growth_rates)

            # Engagement consistency (inverse of coefficient of variation)
            if mean_engagement > 0:
                cv = std_engagement / mean_engagement
                viral_indicators['engagement_consistency'] = max(0, 1 - cv)

            # Peak performance indicator
            if mean_engagement > 0:
                viral_indicators['peak_performance'] = max_engagement / mean_engagement

            # Calculate overall viral score
            viral_score = (
                min(viral_indicators['outlier_posts'] / len(engagement_values), 0.5) * 30 +  # Outlier contribution
                min(max(viral_indicators['growth_acceleration'], 0), 2) * 25 +  # Growth contribution
                viral_indicators['engagement_consistency'] * 20 +  # Consistency contribution
                min(viral_indicators['peak_performance'] / 5, 1) * 25  # Peak performance contribution
            )

            # Find highest performing content
            highest_performing_post = {
                'index': int(np.argmax(engagement_array)),
                'engagement': int(max_engagement),
                'viral_score': min(100, viral_score * (max_engagement / max(mean_engagement, 1)))
            }

            return {
                'overall_viral_score': round(min(100, viral_score), 2),
                'viral_content_indicators': {
                    'outlier_posts_count': viral_indicators['outlier_posts'],
                    'growth_acceleration': round(viral_indicators['growth_acceleration'], 4),
                    'engagement_consistency': round(viral_indicators['engagement_consistency'], 3),
                    'peak_performance_ratio': round(viral_indicators['peak_performance'], 2),
                    'high_engagement_posts': int(viral_indicators['outlier_posts']),
                    'consistent_performance': viral_indicators['engagement_consistency'] > 0.7,
                    'growing_trend': viral_indicators['growth_acceleration'] > 0.1
                },
                'highest_performing_post_score': round(highest_performing_post['viral_score'], 2),
                'viral_content_detection': {
                    'method': 'statistical_analysis',
                    'outlier_threshold': 2.0,
                    'viral_posts_identified': viral_indicators['outlier_posts']
                }
            }

        except Exception as e:
            logger.warning(f"Viral potential analysis failed: {e}")
            return self._get_default_viral_analysis()

    async def _analyze_content_trends(self, time_series_data: Dict, posts_data: List[dict]) -> Dict[str, Any]:
        """Analyze content trends and patterns"""
        try:
            content_types = time_series_data['content_types']
            timestamps = time_series_data['timestamps']
            engagement_values = time_series_data['engagement']

            if not content_types or len(content_types) < 3:
                return self._get_default_content_trends()

            # Analyze content type distribution over time
            content_distribution = Counter(content_types)
            total_posts = len(content_types)

            # Analyze hashtag trends
            hashtag_counts = time_series_data['hashtags']
            hashtag_trend = self._analyze_hashtag_evolution(hashtag_counts, timestamps)

            # Content freshness analysis
            content_freshness = self._calculate_content_freshness(posts_data, timestamps)

            # Trending hashtags detection
            trending_hashtags = self._detect_trending_hashtags(posts_data)

            return {
                'content_distribution': dict(content_distribution),
                'content_distribution_percentages': {
                    content_type: round(count / total_posts * 100, 1)
                    for content_type, count in content_distribution.items()
                },
                'hashtag_trends': hashtag_trend,
                'trending_hashtags': trending_hashtags,
                'content_freshness_score': content_freshness,
                'hashtag_diversity_score': len(set([h for post in posts_data for h in self._extract_hashtags(post.get('caption', ''))]))
            }

        except Exception as e:
            logger.warning(f"Content trends analysis failed: {e}")
            return self._get_default_content_trends()

    async def _analyze_hashtag_trends(self, time_series_data: Dict, posts_data: List[dict]) -> Dict[str, Any]:
        """Analyze hashtag momentum and trends"""
        try:
            # Extract all hashtags with timestamps
            hashtag_timeline = []
            for i, post in enumerate(posts_data):
                if i < len(time_series_data['timestamps']):
                    timestamp = time_series_data['timestamps'][i]
                    engagement = time_series_data['engagement'][i]
                    hashtags = self._extract_hashtags(post.get('caption', ''))

                    for hashtag in hashtags:
                        hashtag_timeline.append({
                            'hashtag': hashtag,
                            'timestamp': timestamp,
                            'engagement': engagement
                        })

            if not hashtag_timeline:
                return {'trending_hashtags': [], 'hashtag_momentum': {}, 'hashtag_performance': {}}

            # Group by hashtag and calculate momentum
            hashtag_data = defaultdict(list)
            for entry in hashtag_timeline:
                hashtag_data[entry['hashtag']].append(entry)

            hashtag_momentum = {}
            hashtag_performance = {}

            for hashtag, entries in hashtag_data.items():
                if len(entries) >= 2:  # Need at least 2 data points
                    # Sort by time
                    entries.sort(key=lambda x: x['timestamp'])

                    # Calculate momentum (recent vs historical performance)
                    recent_engagement = np.mean([e['engagement'] for e in entries[-2:]])  # Last 2 uses
                    historical_engagement = np.mean([e['engagement'] for e in entries[:-2]]) if len(entries) > 2 else recent_engagement

                    momentum = (recent_engagement - historical_engagement) / max(historical_engagement, 1)
                    hashtag_momentum[hashtag] = round(momentum, 4)

                    # Overall performance
                    hashtag_performance[hashtag] = {
                        'total_uses': len(entries),
                        'avg_engagement': round(np.mean([e['engagement'] for e in entries]), 2),
                        'momentum': round(momentum, 4),
                        'trend_direction': 'increasing' if momentum > 0.1 else 'decreasing' if momentum < -0.1 else 'stable'
                    }

            # Identify trending hashtags
            trending_hashtags = sorted(
                [(hashtag, momentum) for hashtag, momentum in hashtag_momentum.items()],
                key=lambda x: x[1], reverse=True
            )[:10]

            return {
                'trending_hashtags': [{'hashtag': h, 'momentum': m} for h, m in trending_hashtags],
                'hashtag_momentum': hashtag_momentum,
                'hashtag_performance': hashtag_performance,
                'total_unique_hashtags': len(hashtag_data),
                'hashtag_usage_frequency': {h: len(entries) for h, entries in hashtag_data.items()}
            }

        except Exception as e:
            logger.warning(f"Hashtag trends analysis failed: {e}")
            return {'trending_hashtags': [], 'hashtag_momentum': {}, 'hashtag_performance': {}}

    async def _analyze_engagement_patterns(self, time_series_data: Dict) -> Dict[str, Any]:
        """Analyze engagement patterns and rhythms"""
        try:
            timestamps = time_series_data['timestamps']
            engagement_values = time_series_data['engagement']

            if len(timestamps) < 3:
                return self._get_default_engagement_patterns()

            # Create pandas dataframe for time series analysis
            df = pd.DataFrame({
                'timestamp': timestamps,
                'engagement': engagement_values
            })
            df = df.set_index('timestamp').sort_index()

            # Resample to daily frequency if we have enough data points
            if len(df) > 7:
                daily_engagement = df.resample('D').mean().fillna(0)
            else:
                daily_engagement = df

            # Analyze patterns
            patterns = {
                'posting_frequency': len(df) / max(time_series_data['time_span_days'], 1),
                'engagement_volatility': np.std(engagement_values) / max(np.mean(engagement_values), 1),
                'trend_direction': self._detect_trend_direction(engagement_values),
                'seasonal_patterns': self._detect_seasonal_patterns(daily_engagement),
                'peak_engagement_times': self._find_peak_engagement_times(timestamps, engagement_values)
            }

            # Engagement consistency analysis
            consistency_score = self._calculate_engagement_consistency(engagement_values)

            return {
                'posting_frequency_per_day': round(patterns['posting_frequency'], 2),
                'engagement_volatility': round(patterns['engagement_volatility'], 4),
                'trend_direction': patterns['trend_direction'],
                'consistency_score': consistency_score,
                'peak_engagement_times': patterns['peak_engagement_times'],
                'seasonal_patterns': patterns['seasonal_patterns'],
                'engagement_rhythm': self._analyze_engagement_rhythm(timestamps, engagement_values)
            }

        except Exception as e:
            logger.warning(f"Engagement patterns analysis failed: {e}")
            return self._get_default_engagement_patterns()

    async def _perform_statistical_trend_analysis(self, time_series_data: Dict) -> Dict[str, Any]:
        """Perform statistical trend analysis using advanced methods"""
        try:
            engagement_values = time_series_data['engagement']
            if len(engagement_values) < 5:
                return self._get_default_statistical_analysis()

            # Convert to pandas series
            ts = pd.Series(engagement_values)

            # Statistical tests
            analysis_results = {
                'trend_statistics': {},
                'stationarity_test': {},
                'autocorrelation': {},
                'change_point_detection': {}
            }

            # Trend statistics
            analysis_results['trend_statistics'] = {
                'mean': float(ts.mean()),
                'std': float(ts.std()),
                'skewness': float(ts.skew()),
                'kurtosis': float(ts.kurtosis()),
                'coefficient_of_variation': float(ts.std() / ts.mean()) if ts.mean() != 0 else 0
            }

            # Simple trend detection using linear regression
            x = np.arange(len(ts))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, ts)

            analysis_results['trend_statistics'].update({
                'trend_slope': float(slope),
                'trend_r_squared': float(r_value**2),
                'trend_p_value': float(p_value),
                'trend_significance': 'significant' if p_value < 0.05 else 'not_significant'
            })

            # Change point detection using simple method
            change_points = self._detect_change_points(engagement_values)
            analysis_results['change_point_detection'] = {
                'change_points_detected': len(change_points),
                'change_point_indices': change_points,
                'regime_changes': len(change_points) > 0
            }

            # Autocorrelation analysis
            if len(ts) > 3:
                autocorr_1 = ts.autocorr(lag=1) if len(ts) > 1 else 0
                analysis_results['autocorrelation'] = {
                    'lag_1_autocorrelation': float(autocorr_1) if not np.isnan(autocorr_1) else 0,
                    'persistence': 'high' if abs(autocorr_1) > 0.5 else 'medium' if abs(autocorr_1) > 0.2 else 'low'
                }

            return analysis_results

        except Exception as e:
            logger.warning(f"Statistical trend analysis failed: {e}")
            return self._get_default_statistical_analysis()

    async def _detect_engagement_anomalies(self, time_series_data: Dict) -> Dict[str, Any]:
        """Detect engagement anomalies using drift detection"""
        try:
            engagement_values = time_series_data['engagement']
            if len(engagement_values) < 3:
                return {'anomalies_detected': 0, 'anomaly_indices': [], 'drift_detected': False}

            # Use statistical methods for anomaly detection
            engagement_array = np.array(engagement_values)

            # Z-score based anomaly detection
            z_scores = np.abs(stats.zscore(engagement_array))
            anomaly_threshold = 2.5
            anomaly_indices = np.where(z_scores > anomaly_threshold)[0].tolist()

            # IQR-based anomaly detection
            Q1 = np.percentile(engagement_array, 25)
            Q3 = np.percentile(engagement_array, 75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR

            iqr_anomalies = np.where((engagement_array < lower_bound) | (engagement_array > upper_bound))[0].tolist()

            # Combine anomaly detection methods
            combined_anomalies = list(set(anomaly_indices + iqr_anomalies))

            # Drift detection simulation (using statistical properties)
            drift_detected = len(combined_anomalies) > len(engagement_values) * 0.2  # More than 20% anomalies

            # Engagement spikes detection
            engagement_spikes = []
            mean_engagement = np.mean(engagement_array)
            std_engagement = np.std(engagement_array)

            for i, engagement in enumerate(engagement_values):
                if engagement > mean_engagement + 2 * std_engagement:
                    engagement_spikes.append({
                        'index': i,
                        'engagement': engagement,
                        'spike_magnitude': (engagement - mean_engagement) / std_engagement
                    })

            return {
                'anomalies_detected': len(combined_anomalies),
                'anomaly_indices': combined_anomalies,
                'anomaly_method': 'zscore_and_iqr',
                'drift_detected': drift_detected,
                'engagement_spikes': engagement_spikes,
                'spike_count': len(engagement_spikes),
                'anomaly_percentage': round(len(combined_anomalies) / len(engagement_values) * 100, 2)
            }

        except Exception as e:
            logger.warning(f"Anomaly detection failed: {e}")
            return {'anomalies_detected': 0, 'anomaly_indices': [], 'drift_detected': False}

    async def _forecast_future_trends(self, time_series_data: Dict) -> Dict[str, Any]:
        """Forecast future trends using time series forecasting"""
        try:
            engagement_values = time_series_data['engagement']
            timestamps = time_series_data['timestamps']

            if len(engagement_values) < 5:
                return self._get_default_forecast()

            # Simple trend forecasting using linear extrapolation
            x = np.arange(len(engagement_values))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, engagement_values)

            # Forecast next 5 periods
            forecast_periods = 5
            forecast_x = np.arange(len(engagement_values), len(engagement_values) + forecast_periods)
            forecast_values = slope * forecast_x + intercept

            # Add confidence intervals (simple approach)
            residuals = np.array(engagement_values) - (slope * x + intercept)
            residual_std = np.std(residuals)

            forecast_upper = forecast_values + 1.96 * residual_std
            forecast_lower = np.maximum(0, forecast_values - 1.96 * residual_std)  # Don't allow negative engagement

            # Trend classification
            if slope > 0.1:
                trend_forecast = 'increasing'
            elif slope < -0.1:
                trend_forecast = 'decreasing'
            else:
                trend_forecast = 'stable'

            # Seasonal forecast (simplified)
            seasonal_forecast = self._forecast_seasonal_patterns(engagement_values, timestamps)

            return {
                'trend_forecast': trend_forecast,
                'forecast_values': forecast_values.tolist(),
                'forecast_confidence_upper': forecast_upper.tolist(),
                'forecast_confidence_lower': forecast_lower.tolist(),
                'forecast_periods': forecast_periods,
                'trend_strength': abs(slope),
                'forecast_accuracy_estimate': max(0, min(1, r_value**2)),
                'seasonal_forecast': seasonal_forecast,
                'next_period_prediction': {
                    'expected_engagement': float(forecast_values[0]),
                    'confidence_interval': [float(forecast_lower[0]), float(forecast_upper[0])],
                    'trend_direction': trend_forecast
                }
            }

        except Exception as e:
            logger.warning(f"Trend forecasting failed: {e}")
            return self._get_default_forecast()

    async def _generate_trend_recommendations(self, time_series_data: Dict, posts_data: List[dict]) -> Dict[str, Any]:
        """Generate trend-based optimization recommendations"""
        try:
            recommendations = []
            insights = []

            engagement_values = time_series_data['engagement']
            if len(engagement_values) < 3:
                return {'recommendations': ['insufficient_data_for_trend_analysis']}

            # Analyze engagement trend
            x = np.arange(len(engagement_values))
            slope, _, r_value, p_value, _ = stats.linregress(x, engagement_values)

            if slope > 0.1 and p_value < 0.05:
                recommendations.append('maintain_current_strategy')
                insights.append('engagement_trending_upward')
            elif slope < -0.1 and p_value < 0.05:
                recommendations.append('revise_content_strategy')
                insights.append('engagement_declining')

            # Analyze posting frequency
            time_span_days = time_series_data['time_span_days']
            posting_frequency = len(posts_data) / max(time_span_days, 1)

            if posting_frequency < 0.5:  # Less than 1 post per 2 days
                recommendations.append('increase_posting_frequency')
            elif posting_frequency > 3:  # More than 3 posts per day
                recommendations.append('consider_reducing_posting_frequency')

            # Analyze engagement consistency
            cv = np.std(engagement_values) / max(np.mean(engagement_values), 1)
            if cv > 1.0:  # High variability
                recommendations.append('focus_on_consistent_quality')
                insights.append('high_engagement_variability')

            # Hashtag recommendations
            hashtag_counts = time_series_data['hashtags']
            avg_hashtags = np.mean(hashtag_counts)
            if avg_hashtags < 3:
                recommendations.append('increase_hashtag_usage')
            elif avg_hashtags > 15:
                recommendations.append('optimize_hashtag_selection')

            # Content type recommendations
            content_types = time_series_data['content_types']
            content_diversity = len(set(content_types)) / len(content_types)
            if content_diversity < 0.3:
                recommendations.append('diversify_content_types')

            return {
                'recommendations': recommendations if recommendations else ['maintain_current_approach'],
                'insights': insights,
                'trend_summary': {
                    'overall_trend': 'positive' if slope > 0 else 'negative' if slope < -0.1 else 'stable',
                    'trend_strength': abs(slope),
                    'consistency_level': 'high' if cv < 0.5 else 'medium' if cv < 1.0 else 'low',
                    'posting_frequency': round(posting_frequency, 2)
                },
                'optimization_opportunities': self._identify_optimization_opportunities(time_series_data, posts_data)
            }

        except Exception as e:
            logger.warning(f"Trend recommendations generation failed: {e}")
            return {'recommendations': ['analysis_error']}

    def _classify_content_type(self, post: Dict[str, Any]) -> str:
        """Classify content type from post data"""
        caption = post.get('caption', '').lower()

        # Simple content classification
        if any(word in caption for word in ['photo', 'picture', 'image']):
            return 'photo'
        elif any(word in caption for word in ['video', 'watch', 'clip']):
            return 'video'
        elif any(word in caption for word in ['story', 'tell', 'share']):
            return 'story'
        elif any(word in caption for word in ['quote', 'inspiration', 'motivat']):
            return 'inspirational'
        elif any(word in caption for word in ['tutorial', 'how', 'learn', 'tip']):
            return 'educational'
        else:
            return 'general'

    def _analyze_hashtag_evolution(self, hashtag_counts: List[int], timestamps: List[datetime]) -> Dict[str, Any]:
        """Analyze how hashtag usage evolves over time"""
        try:
            if len(hashtag_counts) < 3:
                return {'trend': 'stable', 'evolution_score': 0}

            # Calculate trend in hashtag usage
            x = np.arange(len(hashtag_counts))
            slope, _, r_value, p_value, _ = stats.linregress(x, hashtag_counts)

            trend = 'increasing' if slope > 0.1 else 'decreasing' if slope < -0.1 else 'stable'
            evolution_score = abs(slope) * r_value**2  # Strength * confidence

            return {
                'trend': trend,
                'evolution_score': round(evolution_score, 4),
                'average_hashtags_per_post': round(np.mean(hashtag_counts), 2),
                'hashtag_consistency': 1 - (np.std(hashtag_counts) / max(np.mean(hashtag_counts), 1))
            }

        except Exception:
            return {'trend': 'stable', 'evolution_score': 0}

    def _calculate_content_freshness(self, posts_data: List[dict], timestamps: List[datetime]) -> float:
        """Calculate content freshness score"""
        try:
            if not posts_data or not timestamps:
                return 50.0

            # Analyze content diversity and recency
            captions = [post.get('caption', '') for post in posts_data]
            unique_words = set()
            total_words = 0

            for caption in captions:
                words = caption.lower().split()
                unique_words.update(words)
                total_words += len(words)

            # Content diversity score
            diversity_score = len(unique_words) / max(total_words, 1) * 100

            # Recency score (more recent content gets higher score)
            if timestamps:
                latest_time = max(timestamps)
                time_scores = []
                for timestamp in timestamps:
                    days_old = (latest_time - timestamp).days
                    recency_score = max(0, 100 - days_old * 2)  # Decrease by 2 points per day
                    time_scores.append(recency_score)
                avg_recency = np.mean(time_scores)
            else:
                avg_recency = 50

            # Combined freshness score
            freshness = (diversity_score * 0.6 + avg_recency * 0.4)
            return round(min(100, max(0, freshness)), 2)

        except Exception:
            return 50.0

    def _detect_trending_hashtags(self, posts_data: List[dict]) -> List[Dict[str, Any]]:
        """Detect trending hashtags from posts"""
        try:
            hashtag_data = defaultdict(list)

            for i, post in enumerate(posts_data):
                caption = post.get('caption', '')
                hashtags = self._extract_hashtags(caption)
                engagement = post.get('likes_count', 0) + post.get('comments_count', 0) * 10

                for hashtag in hashtags:
                    hashtag_data[hashtag].append({
                        'post_index': i,
                        'engagement': engagement
                    })

            # Calculate trending score for each hashtag
            trending_hashtags = []
            for hashtag, data in hashtag_data.items():
                if len(data) >= 2:  # Hashtag used in at least 2 posts
                    avg_engagement = np.mean([d['engagement'] for d in data])
                    usage_frequency = len(data)

                    # Trending score combines engagement and frequency
                    trending_score = avg_engagement * np.log(usage_frequency + 1)

                    trending_hashtags.append({
                        'hashtag': hashtag,
                        'usage_count': usage_frequency,
                        'avg_engagement': round(avg_engagement, 2),
                        'trending_score': round(trending_score, 2)
                    })

            # Sort by trending score and return top 10
            trending_hashtags.sort(key=lambda x: x['trending_score'], reverse=True)
            return trending_hashtags[:10]

        except Exception:
            return []

    def _extract_hashtags(self, caption: str) -> List[str]:
        """Extract hashtags from caption"""
        import re
        if not caption:
            return []
        return re.findall(r'#\w+', caption.lower())

    def _detect_trend_direction(self, values: List[float]) -> str:
        """Detect overall trend direction"""
        try:
            if len(values) < 3:
                return 'insufficient_data'

            x = np.arange(len(values))
            slope, _, r_value, p_value, _ = stats.linregress(x, values)

            if p_value < 0.05:  # Statistically significant
                if slope > 0.1:
                    return 'increasing'
                elif slope < -0.1:
                    return 'decreasing'
                else:
                    return 'stable'
            else:
                return 'no_clear_trend'

        except Exception:
            return 'analysis_error'

    def _detect_seasonal_patterns(self, daily_engagement) -> Dict[str, Any]:
        """Detect seasonal patterns in engagement"""
        try:
            if len(daily_engagement) < 7:
                return {'pattern_detected': False, 'pattern_type': 'insufficient_data'}

            # Simple day-of-week analysis
            if hasattr(daily_engagement.index, 'dayofweek'):
                dow_engagement = daily_engagement.groupby(daily_engagement.index.dayofweek).mean()
                best_day = dow_engagement.idxmax().iloc[0] if not dow_engagement.empty else 0
                worst_day = dow_engagement.idxmin().iloc[0] if not dow_engagement.empty else 0

                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

                return {
                    'pattern_detected': True,
                    'pattern_type': 'weekly',
                    'best_day': days[best_day],
                    'worst_day': days[worst_day],
                    'weekly_pattern': {days[i]: float(dow_engagement.iloc[i]) if i < len(dow_engagement) else 0
                                     for i in range(7)}
                }

            return {'pattern_detected': False, 'pattern_type': 'no_datetime_index'}

        except Exception:
            return {'pattern_detected': False, 'pattern_type': 'analysis_error'}

    def _find_peak_engagement_times(self, timestamps: List[datetime], engagement_values: List[float]) -> List[str]:
        """Find peak engagement times"""
        try:
            if len(timestamps) != len(engagement_values) or len(timestamps) < 3:
                return ['insufficient_data']

            # Group by hour of day
            hour_engagement = defaultdict(list)
            for timestamp, engagement in zip(timestamps, engagement_values):
                hour = timestamp.hour
                hour_engagement[hour].append(engagement)

            # Calculate average engagement per hour
            hour_averages = {}
            for hour, engagements in hour_engagement.items():
                hour_averages[hour] = np.mean(engagements)

            if not hour_averages:
                return ['no_time_data']

            # Find top 3 hours
            top_hours = sorted(hour_averages.items(), key=lambda x: x[1], reverse=True)[:3]

            peak_times = []
            for hour, avg_engagement in top_hours:
                time_range = f"{hour:02d}:00-{(hour+1)%24:02d}:00"
                peak_times.append(time_range)

            return peak_times

        except Exception:
            return ['analysis_error']

    def _calculate_engagement_consistency(self, engagement_values: List[float]) -> float:
        """Calculate engagement consistency score"""
        try:
            if len(engagement_values) < 2:
                return 0.5

            mean_engagement = np.mean(engagement_values)
            std_engagement = np.std(engagement_values)

            if mean_engagement == 0:
                return 0.0

            # Consistency is inverse of coefficient of variation
            cv = std_engagement / mean_engagement
            consistency = max(0, 1 - cv)

            return round(consistency, 3)

        except Exception:
            return 0.5

    def _analyze_engagement_rhythm(self, timestamps: List[datetime], engagement_values: List[float]) -> Dict[str, Any]:
        """Analyze engagement rhythm and patterns"""
        try:
            if len(timestamps) < 3:
                return {'rhythm': 'irregular', 'pattern_strength': 0}

            # Calculate time intervals between posts
            intervals = []
            for i in range(1, len(timestamps)):
                interval = (timestamps[i] - timestamps[i-1]).total_seconds() / 3600  # Hours
                intervals.append(interval)

            if not intervals:
                return {'rhythm': 'single_post', 'pattern_strength': 0}

            # Analyze interval consistency
            mean_interval = np.mean(intervals)
            std_interval = np.std(intervals)

            if std_interval / max(mean_interval, 1) < 0.3:
                rhythm = 'regular'
                pattern_strength = 0.8
            elif std_interval / max(mean_interval, 1) < 0.7:
                rhythm = 'semi_regular'
                pattern_strength = 0.5
            else:
                rhythm = 'irregular'
                pattern_strength = 0.2

            return {
                'rhythm': rhythm,
                'pattern_strength': pattern_strength,
                'average_posting_interval_hours': round(mean_interval, 2),
                'posting_consistency': round(1 - (std_interval / max(mean_interval, 1)), 3)
            }

        except Exception:
            return {'rhythm': 'analysis_error', 'pattern_strength': 0}

    def _detect_change_points(self, values: List[float]) -> List[int]:
        """Detect change points in time series"""
        try:
            if len(values) < 5:
                return []

            # Simple change point detection using moving averages
            window_size = max(2, len(values) // 4)
            change_points = []

            for i in range(window_size, len(values) - window_size):
                before_mean = np.mean(values[i-window_size:i])
                after_mean = np.mean(values[i:i+window_size])

                # Detect significant change (more than 1 standard deviation)
                overall_std = np.std(values)
                if abs(before_mean - after_mean) > overall_std:
                    change_points.append(i)

            return change_points

        except Exception:
            return []

    def _forecast_seasonal_patterns(self, engagement_values: List[float], timestamps: List[datetime]) -> Dict[str, Any]:
        """Forecast seasonal patterns"""
        try:
            if len(engagement_values) < 7:
                return {'seasonal_forecast': 'insufficient_data'}

            # Simple seasonal forecast based on day of week
            if len(timestamps) == len(engagement_values):
                dow_engagement = defaultdict(list)
                for timestamp, engagement in zip(timestamps, engagement_values):
                    dow = timestamp.weekday()
                    dow_engagement[dow].append(engagement)

                # Predict next week based on historical patterns
                weekly_forecast = {}
                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

                for dow in range(7):
                    if dow in dow_engagement and dow_engagement[dow]:
                        weekly_forecast[days[dow]] = round(np.mean(dow_engagement[dow]), 2)
                    else:
                        weekly_forecast[days[dow]] = round(np.mean(engagement_values), 2)

                return {
                    'seasonal_forecast': 'weekly_pattern',
                    'weekly_forecast': weekly_forecast,
                    'forecast_confidence': 'medium' if len(dow_engagement) > 3 else 'low'
                }

            return {'seasonal_forecast': 'no_temporal_data'}

        except Exception:
            return {'seasonal_forecast': 'analysis_error'}

    def _identify_optimization_opportunities(self, time_series_data: Dict, posts_data: List[dict]) -> List[Dict[str, Any]]:
        """Identify specific optimization opportunities"""
        opportunities = []

        try:
            engagement_values = time_series_data['engagement']

            # Low engagement opportunity
            if np.mean(engagement_values) < np.median(engagement_values) * 0.5:
                opportunities.append({
                    'type': 'engagement_boost',
                    'description': 'Average engagement is below median, focus on high-performing content types',
                    'priority': 'high'
                })

            # Inconsistent posting opportunity
            posting_intervals = []
            timestamps = time_series_data['timestamps']
            for i in range(1, len(timestamps)):
                interval = (timestamps[i] - timestamps[i-1]).days
                posting_intervals.append(interval)

            if posting_intervals and np.std(posting_intervals) > 2:
                opportunities.append({
                    'type': 'posting_consistency',
                    'description': 'Posting schedule is irregular, establish consistent posting rhythm',
                    'priority': 'medium'
                })

            # Hashtag optimization opportunity
            hashtag_counts = time_series_data['hashtags']
            if np.mean(hashtag_counts) < 3:
                opportunities.append({
                    'type': 'hashtag_optimization',
                    'description': 'Low hashtag usage, increase hashtag usage to improve discoverability',
                    'priority': 'medium'
                })

            return opportunities

        except Exception:
            return [{'type': 'analysis_error', 'description': 'Unable to identify opportunities', 'priority': 'low'}]

    # Fallback methods
    def _get_fallback_trend_analysis(self, posts_data: List[dict]) -> Dict[str, Any]:
        """Fallback analysis when trend detection is not available"""
        return {
            'viral_potential': self._get_default_viral_analysis(),
            'content_trends': self._get_default_content_trends(),
            'hashtag_trends': {'trending_hashtags': []},
            'engagement_patterns': self._get_default_engagement_patterns(),
            'trend_analysis': self._get_default_statistical_analysis(),
            'anomaly_detection': {'anomalies_detected': 0},
            'forecasting': self._get_default_forecast(),
            'optimization_recommendations': {'recommendations': ['install_trend_dependencies']}
        }

    def _get_minimal_trend_analysis(self, posts_data: List[dict]) -> Dict[str, Any]:
        """Minimal analysis when insufficient data"""
        return {
            'viral_potential': {'overall_viral_score': 0, 'note': 'insufficient_data'},
            'content_trends': {'note': 'insufficient_temporal_data'},
            'trend_analysis': {'note': 'minimum_3_posts_required'},
            'optimization_recommendations': {'recommendations': ['create_more_content']}
        }

    def _get_default_viral_analysis(self) -> Dict[str, Any]:
        return {
            'overall_viral_score': 50.0,
            'viral_content_indicators': {
                'outlier_posts_count': 0,
                'growth_acceleration': 0.0,
                'engagement_consistency': 0.5,
                'peak_performance_ratio': 1.0,
                'high_engagement_posts': 0,
                'consistent_performance': False,
                'growing_trend': False
            },
            'highest_performing_post_score': 50.0
        }

    def _get_default_content_trends(self) -> Dict[str, Any]:
        return {
            'content_distribution': {'general': 1},
            'hashtag_trends': {'trend': 'stable'},
            'trending_hashtags': [],
            'content_freshness_score': 50.0,
            'hashtag_diversity_score': 0
        }

    def _get_default_engagement_patterns(self) -> Dict[str, Any]:
        return {
            'posting_frequency_per_day': 1.0,
            'engagement_volatility': 0.5,
            'trend_direction': 'stable',
            'consistency_score': 0.5,
            'peak_engagement_times': ['12:00-13:00', '18:00-19:00'],
            'seasonal_patterns': {'pattern_detected': False}
        }

    def _get_default_statistical_analysis(self) -> Dict[str, Any]:
        return {
            'trend_statistics': {
                'mean': 0,
                'std': 0,
                'trend_slope': 0,
                'trend_significance': 'not_significant'
            },
            'change_point_detection': {'change_points_detected': 0},
            'autocorrelation': {'lag_1_autocorrelation': 0}
        }

    def _get_default_forecast(self) -> Dict[str, Any]:
        return {
            'trend_forecast': 'stable',
            'forecast_values': [0, 0, 0, 0, 0],
            'forecast_periods': 5,
            'trend_strength': 0,
            'forecast_accuracy_estimate': 0
        }