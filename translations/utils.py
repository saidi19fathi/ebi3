"""
Utilitaires pour le module de traduction.
"""
import hashlib
import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class TranslationUtils:
    """Classe utilitaire pour les opérations communes de traduction."""

    @staticmethod
    def extract_text_from_html(html_content: str) -> str:
        """
        Extrait le texte d'un contenu HTML pour la traduction.

        Args:
            html_content: Contenu HTML

        Returns:
            Texte extrait sans balises HTML
        """
        if not html_content:
            return ""

        # Supprime les balises HTML mais conserve le texte
        text = strip_tags(html_content)

        # Nettoie les espaces multiples
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    @staticmethod
    def inject_translation_into_html(original_html: str, translated_text: str) -> str:
        """
        Injecte un texte traduit dans une structure HTML.
        Version simplifiée - à améliorer pour des cas complexes.

        Args:
            original_html: HTML original
            translated_text: Texte traduit

        Returns:
            HTML avec texte traduit
        """
        if not original_html or not translated_text:
            return original_html or translated_text

        # Si le HTML original est simple (pas de balises), retourne le texte traduit
        if '<' not in original_html and '>' not in original_html:
            return translated_text

        # Pour l'instant, retourne le texte traduit tel quel
        # À améliorer avec un système de préservation des balises
        return translated_text

    @staticmethod
    def should_exclude_from_translation(text: str, field_name: str = '') -> bool:
        """
        Détermine si un texte doit être exclu de la traduction.

        Args:
            text: Texte à vérifier
            field_name: Nom du champ (pour les exclusions spécifiques)

        Returns:
            True si le texte doit être exclu
        """
        if not text or not isinstance(text, str):
            return True

        # Exclusions par longueur
        if len(text.strip()) < 3:
            return True

        # Exclusions par type de contenu
        exclusions = [
            # URLs
            r'^https?://[^\s]+$',
            # Emails
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            # Codes techniques
            r'^[A-Z0-9_]{5,}$',
            # Nombres seuls
            r'^\d+$',
            # Codes hexadécimaux
            r'^#[0-9A-Fa-f]{3,6}$',
        ]

        for pattern in exclusions:
            if re.match(pattern, text.strip()):
                return True

        # Exclusions par nom de champ
        field_exclusions = ['url', 'email', 'password', 'token', 'key', 'secret', 'id']
        if any(excl in field_name.lower() for excl in field_exclusions):
            return True

        # Contenu principalement numérique
        digit_ratio = sum(1 for c in text if c.isdigit()) / len(text)
        if digit_ratio > 0.7:  # 70% de chiffres
            return True

        return False

    @staticmethod
    def calculate_text_complexity(text: str) -> float:
        """
        Calcule la complexité d'un texte pour prioriser les traductions.

        Args:
            text: Texte à analyser

        Returns:
            Score de complexité entre 0 et 1
        """
        if not text:
            return 0.0

        length_score = min(len(text) / 1000, 1.0)  # Normalisé sur 1000 caractères

        # Densité de mots uniques
        words = re.findall(r'\b\w+\b', text.lower())
        if words:
            unique_ratio = len(set(words)) / len(words)
        else:
            unique_ratio = 0.5

        # Présence de balises HTML
        html_score = 0.2 if '<' in text and '>' in text else 0.0

        # Score combiné
        complexity = (length_score * 0.4 + unique_ratio * 0.4 + html_score * 0.2)

        return min(max(complexity, 0.0), 1.0)

    @staticmethod
    def generate_content_fingerprint(content: Dict) -> str:
        """
        Génère une empreinte unique pour un contenu.

        Args:
            content: Dictionnaire représentant le contenu

        Returns:
            Empreinte MD5
        """
        import json

        # Trie les clés pour garantir la consistance
        sorted_content = json.dumps(content, sort_keys=True)
        return hashlib.md5(sorted_content.encode('utf-8')).hexdigest()

    @staticmethod
    def get_user_translation_limits(user) -> Dict:
        """
        Récupère les limites de traduction pour un utilisateur.

        Args:
            user: Utilisateur Django

        Returns:
            Dictionnaire avec les limites
        """
        limits = {
            'daily_limit': 100,
            'monthly_limit': 1000,
            'max_text_length': 10000,
            'allow_batch': True,
            'batch_size_limit': 10,
        }

        # Ajuste selon le type d'utilisateur
        if user.is_staff:
            limits['daily_limit'] = 1000
            limits['monthly_limit'] = 10000
            limits['batch_size_limit'] = 50

        if user.is_superuser:
            limits['daily_limit'] = 10000
            limits['monthly_limit'] = 100000
            limits['batch_size_limit'] = 100

        return limits

    @staticmethod
    def format_translation_for_display(translated_text: str, original_text: str = '') -> str:
        """
        Formate une traduction pour l'affichage.

        Args:
            translated_text: Texte traduit
            original_text: Texte original (pour référence)

        Returns:
            Texte formaté
        """
        if not translated_text:
            return original_text or ""

        # Nettoie les artefacts de traduction
        text = translated_text.strip()

        # Supprime les préfixes de traduction courants
        prefixes = [
            'Traduction :',
            'Translation:',
            'Traducción:',
            'Übersetzung:',
            'Traduzione:',
        ]

        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        # Capitalise la première lettre si nécessaire
        if text and text[0].islower() and original_text and original_text[0].isupper():
            text = text[0].upper() + text[1:]

        return text


class TranslationCache:
    """Gestionnaire de cache pour les traductions."""

    CACHE_PREFIX = 'translation:'
    DEFAULT_TIMEOUT = 3600  # 1 heure

    @classmethod
    def get(cls, key: str):
        """
        Récupère une valeur du cache.

        Args:
            key: Clé de cache

        Returns:
            Valeur mise en cache ou None
        """
        cache_key = f"{cls.CACHE_PREFIX}{key}"
        return cache.get(cache_key)

    @classmethod
    def set(cls, key: str, value, timeout: int = None):
        """
        Stocke une valeur dans le cache.

        Args:
            key: Clé de cache
            value: Valeur à stocker
            timeout: Durée de vie en secondes
        """
        cache_key = f"{cls.CACHE_PREFIX}{key}"
        timeout = timeout or cls.DEFAULT_TIMEOUT
        cache.set(cache_key, value, timeout)

    @classmethod
    def delete(cls, key: str):
        """
        Supprime une valeur du cache.

        Args:
            key: Clé de cache
        """
        cache_key = f"{cls.CACHE_PREFIX}{key}"
        cache.delete(cache_key)

    @classmethod
    def clear_pattern(cls, pattern: str):
        """
        Supprime toutes les clés correspondant à un motif.

        Args:
            pattern: Motif de recherche
        """
        # Cette méthode nécessite un backend Redis
        # À implémenter selon le backend de cache utilisé
        pass


class LanguageDetector:
    """Détecteur de langue amélioré."""

    # Mots communs par langue (à étendre)
    LANGUAGE_WORDS = {
        'fr': {'le', 'la', 'les', 'un', 'une', 'des', 'et', 'est', 'dans', 'pour'},
        'en': {'the', 'and', 'is', 'in', 'to', 'of', 'a', 'for', 'on', 'with'},
        'ar': {'ال', 'في', 'من', 'على', 'إلى', 'أن', 'كان', 'هذا', 'ذلك', 'هذه'},
        'es': {'el', 'la', 'los', 'las', 'un', 'una', 'y', 'en', 'de', 'que'},
        'de': {'der', 'die', 'das', 'und', 'ist', 'in', 'den', 'von', 'mit', 'sich'},
        'it': {'il', 'la', 'lo', 'gli', 'le', 'un', 'una', 'e', 'in', 'di'},
        'pt': {'o', 'a', 'os', 'as', 'um', 'uma', 'e', 'em', 'de', 'que'},
        'ru': {'и', 'в', 'не', 'на', 'я', 'он', 'с', 'что', 'это', 'как'},
        'zh': {'的', '是', '在', '和', '了', '有', '我', '他', '这', '个'},
        'tr': {'ve', 'bir', 'bu', 'şey', 'için', 'ama', 'gibi', 'de', 'da', 'ki'},
        'nl': {'de', 'het', 'een', 'en', 'is', 'van', 'op', 'te', 'dat', 'die'},
    }

    @classmethod
    def detect(cls, text: str, min_confidence: float = 0.3) -> Optional[str]:
        """
        Détecte la langue d'un texte.

        Args:
            text: Texte à analyser
            min_confidence: Confiance minimum requise

        Returns:
            Code de langue détecté ou None
        """
        if not text or len(text) < 10:
            return None

        text_lower = text.lower()
        scores = {}

        # Compte les mots par langue
        for lang, words in cls.LANGUAGE_WORDS.items():
            score = sum(1 for word in words if f' {word} ' in f' {text_lower} ')
            if score > 0:
                scores[lang] = score

        if not scores:
            return None

        # Normalise les scores
        max_score = max(scores.values())
        normalized_scores = {lang: score/max_score for lang, score in scores.items()}

        # Retourne la meilleure langue si elle dépasse le seuil
        best_lang = max(normalized_scores.items(), key=lambda x: x[1])

        if best_lang[1] >= min_confidence:
            return best_lang[0]

        return None