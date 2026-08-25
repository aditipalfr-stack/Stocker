"""
=============================================================================
DEPRECATION NOTICE:
Financial statement seed data has been COMPLETELY REMOVED from this file.
Financial statements (Quarters, P&L, Balance Sheet, Cash Flow) must NEVER
come from hardcoded data. All financial data is fetched live from Screener.in.

This module now contains ONLY company metadata fallbacks (sector, industry,
description) to enrich Screener profiles when sector tags are needed.
=============================================================================
"""

from typing import Dict, Any, List

DEFAULT_UNIVERSE_SYMBOLS: List[str] = [
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "INFY",
    "ICICIBANK",
    "BHARTIARTL",
    "ITC",
    "LT",
    "TATAMOTORS",
    "HINDUNILVR"
]

# Optional metadata enrichment (Sector & Industry classifications)
COMPANY_METADATA: Dict[str, Dict[str, str]] = {
    "RELIANCE": {
        "sector": "Energy & Conglomerate",
        "industry": "Oil & Gas / Retail / Telecom",
        "about": "Reliance Industries Limited is India's largest private sector enterprise with businesses spanning energy, petrochemicals, retail, digital services (Jio), and new energy."
    },
    "TCS": {
        "sector": "Information Technology",
        "industry": "IT Services & Consulting",
        "about": "Tata Consultancy Services is an IT services, consulting, and business solutions organization partnering with leading global enterprises for over 55 years."
    },
    "HDFCBANK": {
        "sector": "Banking & Financial Services",
        "industry": "Private Sector Bank",
        "about": "HDFC Bank is India's largest private sector bank with a nationwide distribution network of over 8,800 branches serving over 90 million customers."
    },
    "INFY": {
        "sector": "Information Technology",
        "industry": "IT Services & Software Consulting",
        "about": "Infosys is a global leader in next-generation digital services and consulting, powering digital transformations across 56 countries."
    },
    "ICICIBANK": {
        "sector": "Banking & Financial Services",
        "industry": "Private Sector Bank",
        "about": "ICICI Bank is a leading Indian private bank offering comprehensive retail and corporate banking services with industry-leading Return on Assets."
    },
    "BHARTIARTL": {
        "sector": "Telecommunications",
        "industry": "Telecom Services / 5G / Cloud",
        "about": "Bharti Airtel is a global communications solutions provider with over 500 million customers across 17 countries in South Asia and Africa."
    },
    "ITC": {
        "sector": "Consumer Goods / FMCG",
        "industry": "FMCG / Cigarettes / Paperboards / Agri",
        "about": "ITC is one of India's foremost private sector companies with diversified presence in FMCG, Hotels, Paperboards & Packaging, and Agri-business."
    },
    "LT": {
        "sector": "Infrastructure & Engineering",
        "industry": "EPC Projects / Heavy Engineering / Defense",
        "about": "Larsen & Toubro is an Indian multinational conglomerate engaged in EPC projects, hi-tech manufacturing, defense, and technology services."
    },
    "TATAMOTORS": {
        "sector": "Automobile",
        "industry": "Commercial Vehicles / Passenger Vehicles / EV / JLR",
        "about": "Tata Motors Limited is a leading global automobile manufacturer with commercial vehicles, passenger vehicles, electric vehicles, and the luxury Jaguar Land Rover brand."
    },
    "TMPV": {
        "sector": "Automobile",
        "industry": "Passenger Vehicles / EV / JLR",
        "about": "Tata Motors Passenger Vehicles Ltd manufactures passenger cars, SUVs, electric vehicles, and Jaguar Land Rover luxury vehicles."
    },
    "TMCV": {
        "sector": "Automobile",
        "industry": "Commercial Vehicles",
        "about": "Tata Motors Commercial Vehicles Ltd is India's market leader in medium, heavy, and light commercial vehicles and buses."
    },
    "HINDUNILVR": {
        "sector": "Consumer Goods / FMCG",
        "industry": "Home Care / Beauty & Personal Care / Foods",
        "about": "Hindustan Unilever Limited is India's largest Fast Moving Consumer Goods company with over 50+ household brands used by 9 out of 10 Indian households."
    }
}
