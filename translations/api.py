import hashlib
import logging
import time
from typing import Dict, List, Optional
import requests
from django.conf import settings
from django.core.cache import cache
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)
from .models import TranslationMemory, APILog

logger = logging.getLogger(__name__)


class DeepSeekAPIError(Exception):
    pass


class DeepSeekAPIClient:
    DEFAULT_CONFIG = {
        'API_URL': 'https://api.deepseek.com/v1/chat/completions',
        'MODEL': 'deepseek-chat',
        'TIMEOUT': 30,
        'MAX_RETRIES': 3,
        'BATCH_SIZE': 5,
        'RATE_LIMIT_PER_MINUTE': 60,
        'TEMPERATURE': 0.1,
        'MAX_TOKENS': 4000,
    }

    LANGUAGE_MAP = {
        'fr': 'French',
        'en': 'English',
        'ar': 'Arabic',
        'es': 'Spanish',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'zh': 'Chinese',
        'tr': 'Turkish',
        'nl': 'Dutch',
    }

    def __init__(self, api_key: Optional[str] = None):
        self.config = self.DEFAULT_CONFIG.copy()
        if hasattr(settings, 'DEEPSEEK_CONFIG'):
            self.config.update(settings.DEEPSEEK_CONFIG)

        self.api_key = api_key or getattr(settings, 'DEEPSEEK_API_KEY', None)
        if not self.api_key:
            logger.warning("Aucune clé API DeepSeek configurée")

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        })
        self.rate_limit_cache_key = 'deepseek_rate_limit'

    def _check_rate_limit(self) -> bool:
        cache_key = self.rate_limit_cache_key
        current_time = time.time()
        minute_ago = current_time - 60
        request_history = cache.get(cache_key, [])
        recent_requests = [t for t in request_history if t > minute_ago]

        if len(recent_requests) >= self.config['RATE_LIMIT_PER_MINUTE']:
            logger.warning("Rate limit atteint")
            return False

        recent_requests.append(current_time)
        cache.set(cache_key, recent_requests, timeout=60)
        return True

    def _wait_for_rate_limit(self):
        while not self._check_rate_limit():
            time.sleep(1)

    def _get_language_name(self, language_code: str) -> str:
        return self.LANGUAGE_MAP.get(language_code, language_code.capitalize())

    def _generate_text_hash(self, text: str, source_lang: str, target_lang: str) -> str:
        content = f"{text}|{source_lang}|{target_lang}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _check_memory_cache(self, text: str, source_lang: str, target_lang: str) -> Optional[Dict]:
        cache_key = f"translation:{source_lang}:{target_lang}:{hashlib.md5(text.encode()).hexdigest()}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"Cache Redis hit: {cache_key}")
            return {
                'translated_text': cached,
                'from_cache': 'redis',
                'confidence_score': 1.0
            }

        text_hash = self._generate_text_hash(text, source_lang, target_lang)
        try:
            memory = TranslationMemory.objects.get(
                source_text_hash=text_hash,
                source_language=source_lang,
                target_language=target_lang
            )
            memory.usage_count += 1
            memory.save(update_fields=['usage_count'])
            cache.set(cache_key, memory.translated_text, timeout=3600)
            logger.debug(f"Cache DB hit: {text_hash}")
            return {
                'translated_text': memory.translated_text,
                'from_cache': 'database',
                'confidence_score': memory.confidence_score or 0.9
            }
        except TranslationMemory.DoesNotExist:
            return None

    def _save_to_memory_cache(self, text: str, source_lang: str, target_lang: str,
                             translated_text: str, confidence_score: float = None):
        cache_key = f"translation:{source_lang}:{target_lang}:{hashlib.md5(text.encode()).hexdigest()}"
        cache.set(cache_key, translated_text, timeout=3600)

        text_hash = self._generate_text_hash(text, source_lang, target_lang)
        TranslationMemory.objects.update_or_create(
            source_text_hash=text_hash,
            source_language=source_lang,
            target_language=target_lang,
            defaults={
                'translated_text': translated_text,
                'confidence_score': confidence_score,
                'usage_count': 1,
            }
        )

    def _log_api_call(self, endpoint: str, source_lang: str, target_lang: str,
                     character_count: int, success: bool, response_time: float,
                     status_code: int = None, error_message: str = '', cost_estimate: float = None):
        try:
            APILog.objects.create(
                endpoint=endpoint,
                source_language=source_lang,
                target_language=target_lang,
                character_count=character_count,
                success=success,
                response_time=response_time,
                status_code=status_code,
                error_message=error_message[:2000],
                cost_estimate=cost_estimate,
            )
        except Exception as e:
            logger.error(f"Log API error: {e}")

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        INPUT_PRICE_PER_1K = 0.00014
        OUTPUT_PRICE_PER_1K = 0.00028
        input_cost = (input_tokens / 1000) * INPUT_PRICE_PER_1K
        output_cost = (output_tokens / 1000) * OUTPUT_PRICE_PER_1K
        return input_cost + output_cost

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, DeepSeekAPIError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def translate_text(self, text: str, source_lang: str, target_lang: str) -> Dict:
        start_time = time.time()

        if not text or not text.strip():
            raise ValueError("Texte vide")
        if not self.api_key:
            raise DeepSeekAPIError("API key manquante")

        cached_result = self._check_memory_cache(text, source_lang, target_lang)
        if cached_result:
            logger.info(f"Cache: {source_lang}->{target_lang}")
            return cached_result

        self._wait_for_rate_limit()
        source_lang_name = self._get_language_name(source_lang)
        target_lang_name = self._get_language_name(target_lang)

        prompt = f"""Traduis de {source_lang_name} à {target_lang_name}.
Conserve format, HTML, liens, nombres.
Pas de modification noms propres, codes, emails, URLs.

Texte:
{text}

Traduction en {target_lang_name}:"""

        payload = {
            'model': self.config['MODEL'],
            'messages': [
                {'role': 'system', 'content': 'Traducteur professionnel.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': self.config['TEMPERATURE'],
            'max_tokens': self.config['MAX_TOKENS'],
            'stream': False,
        }

        try:
            logger.debug(f"API call: {source_lang}->{target_lang}, {len(text)} chars")
            response = self.session.post(
                self.config['API_URL'],
                json=payload,
                timeout=self.config['TIMEOUT']
            )
            response_time = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                translated_text = result['choices'][0]['message']['content'].strip()
                translated_text = self._clean_translation(translated_text, text)

                usage = result.get('usage', {})
                input_tokens = usage.get('prompt_tokens', 0)
                output_tokens = usage.get('completion_tokens', 0)
                cost_estimate = self._calculate_cost(input_tokens, output_tokens)
                confidence_score = self._calculate_confidence_score(text, translated_text)

                self._save_to_memory_cache(text, source_lang, target_lang, translated_text, confidence_score)

                self._log_api_call(
                    endpoint='translate',
                    source_lang=source_lang,
                    target_lang=target_lang,
                    character_count=len(text),
                    success=True,
                    response_time=response_time,
                    status_code=response.status_code,
                    cost_estimate=cost_estimate
                )

                logger.info(f"Success: {source_lang}->{target_lang}, {response_time:.2f}s")

                return {
                    'translated_text': translated_text,
                    'from_cache': False,
                    'confidence_score': confidence_score,
                    'api_usage': {
                        'input_tokens': input_tokens,
                        'output_tokens': output_tokens,
                        'total_tokens': usage.get('total_tokens', 0),
                        'cost_estimate': cost_estimate,
                    },
                    'response_time': response_time,
                }
            else:
                error_msg = f"API Error {response.status_code}: {response.text}"
                logger.error(error_msg)
                self._log_api_call(
                    endpoint='translate',
                    source_lang=source_lang,
                    target_lang=target_lang,
                    character_count=len(text),
                    success=False,
                    response_time=response_time,
                    status_code=response.status_code,
                    error_message=response.text[:500],
                )
                raise DeepSeekAPIError(error_msg)

        except requests.RequestException as e:
            response_time = time.time() - start_time
            logger.error(f"Network error: {e}")
            self._log_api_call(
                endpoint='translate',
                source_lang=source_lang,
                target_lang=target_lang,
                character_count=len(text),
                success=False,
                response_time=response_time,
                error_message=str(e),
            )
            raise DeepSeekAPIError(f"Network error: {e}")

    def translate_batch(self, texts: List[str], source_lang: str, target_lang: str) -> List[Dict]:
        results = []
        batch_size = self.config.get('BATCH_SIZE', 5)

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"Batch {i//batch_size + 1}: {len(batch)} texts")

            for text in batch:
                try:
                    result = self.translate_text(text, source_lang, target_lang)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Batch error: {e}")
                    results.append({
                        'translated_text': text,
                        'from_cache': False,
                        'confidence_score': 0.0,
                        'error': str(e),
                        'success': False,
                    })

            if i + batch_size < len(texts):
                time.sleep(0.5)

        return results

    def _clean_translation(self, translated_text: str, original_text: str) -> str:
        lines = translated_text.split('\n')
        cleaned_lines = []
        for line in lines:
            if not any(marker in line.lower() for marker in ['traduction', 'translation', '```']):
                cleaned_lines.append(line)
        cleaned_text = '\n'.join(cleaned_lines).strip()
        return cleaned_text if cleaned_text else original_text

    def _calculate_confidence_score(self, original: str, translated: str) -> float:
        if not original or not translated:
            return 0.0

        orig_len = len(original)
        trans_len = len(translated)
        length_ratio = min(trans_len / orig_len, orig_len / trans_len)

        if '<' in original and '>' in original:
            orig_tags = set(original.split('<')[1:])
            trans_tags = set(translated.split('<')[1:])
            tag_preservation = len(orig_tags & trans_tags) / max(len(orig_tags), 1)
            score = (length_ratio * 0.6 + tag_preservation * 0.4)
        else:
            score = length_ratio

        return min(max(score, 0.0), 1.0)

    def get_supported_languages(self) -> List[str]:
        return list(self.LANGUAGE_MAP.keys())

    def test_connection(self) -> bool:
        try:
            result = self.translate_text("Hello", "en", "fr")
            return bool(result.get('translated_text'))
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


_api_client = None

def get_api_client() -> DeepSeekAPIClient:
    global _api_client
    if _api_client is None:
        _api_client = DeepSeekAPIClient()
    return _api_client