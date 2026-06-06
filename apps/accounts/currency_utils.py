import logging
import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Fallback rate if API fails
DEFAULT_USD_TO_INR_RATE = 95.16  # Using the latest market rate found

def get_usd_to_inr_rate():
    """
    Fetches the current USD to INR exchange rate.
    Uses Django cache to avoid repeated API calls.
    """
    cache_key = "usd_to_inr_rate"
    rate = cache.get(cache_key)
    
    if rate is not None:
        return float(rate)
    
    try:
        # Using a free public API (ExchangeRate-API)
        # Note: In production, consider using a more robust service with an API key
        response = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
        if response.status_code == 200:
            data = response.json()
            rate = data.get("rates", {}).get("INR")
            if rate:
                # Cache the rate for 1 hour (3600 seconds)
                cache.set(cache_key, float(rate), 3600)
                logger.info(f"Updated USD to INR rate from API: {rate}")
                return float(rate)
    except Exception as e:
        logger.error(f"Error fetching exchange rate: {e}")
    
    # Fallback to default if API fails or rate is not found
    return DEFAULT_USD_TO_INR_RATE

def convert_inr_to_usd(inr_amount):
    """Converts INR amount to USD based on current market rate."""
    rate = get_usd_to_inr_rate()
    return round(float(inr_amount) / rate, 2)

def convert_usd_to_inr(usd_amount):
    """Converts USD amount to INR based on current market rate."""
    rate = get_usd_to_inr_rate()
    return round(float(usd_amount) * rate, 2)
