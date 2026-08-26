"""
=============================================================================
Stocker V2 Universe Metadata
=============================================================================
This module contains company classifications and metadata for the 10 Anchor
MVP Stocks across diverse Indian sectors (Energy, IT, EPC, Banking, Auto, FMCG, Metals).
Financial statements are ALWAYS fetched live/cached from official primary sources.
=============================================================================
"""

from typing import Dict, Any, List

DEFAULT_UNIVERSE_SYMBOLS: List[str] = [
    "RELIANCE",
    "TCS",
    "INFY",
    "LT",
    "HDFCBANK",
    "ICICIBANK",
    "TATAMOTORS",
    "HINDUNILVR",
    "ITC",
    "TATASTEEL"
]

COMPANY_METADATA: Dict[str, Dict[str, str]] = {
    "RELIANCE": {
        "sector": "Energy & Conglomerate",
        "industry": "Oil & Gas / Retail / Telecom",
        "about": "Reliance Industries Limited is India's largest private sector enterprise spanning energy, petrochemicals, organized retail, digital services (Jio), and new energy gigafactories."
    },
    "TCS": {
        "sector": "Information Technology",
        "industry": "IT Services & Consulting",
        "about": "Tata Consultancy Services is an IT services, consulting, and business solutions leader partnering with the world's largest businesses in their transformation journeys."
    },
    "INFY": {
        "sector": "Information Technology",
        "industry": "IT Services & Cloud Digital Transformation",
        "about": "Infosys is a global leader in next-generation digital services and consulting, enabling clients across 56 countries to navigate their digital transformation."
    },
    "LT": {
        "sector": "Infrastructure & Engineering",
        "industry": "EPC Projects / Heavy Engineering / Defense",
        "about": "Larsen & Toubro is a technology, engineering, construction, manufacturing, and financial services conglomerate with global EPC operations."
    },
    "HDFCBANK": {
        "sector": "Banking & Financial Services",
        "industry": "Private Sector Bank",
        "about": "HDFC Bank is India's largest private sector bank with a nationwide distribution network of over 8,800 branches serving over 90 million customers."
    },
    "ICICIBANK": {
        "sector": "Banking & Financial Services",
        "industry": "Private Sector Bank",
        "about": "ICICI Bank is a leading Indian private bank offering comprehensive retail and corporate banking services with industry-leading return on assets (ROA)."
    },
    "TATAMOTORS": {
        "sector": "Automobile",
        "industry": "Commercial Vehicles / Passenger Vehicles / EV / JLR",
        "about": "Tata Motors Limited is a leading global automobile manufacturer with commercial vehicles, passenger vehicles, electric vehicles, and luxury Jaguar Land Rover vehicles."
    },
    "HINDUNILVR": {
        "sector": "Consumer Goods / FMCG",
        "industry": "Home Care / Beauty & Personal Care / Foods",
        "about": "Hindustan Unilever Limited is India's largest Fast Moving Consumer Goods company with over 50+ household brands used by 9 out of 10 Indian households."
    },
    "ITC": {
        "sector": "Consumer Goods / FMCG",
        "industry": "FMCG / Cigarettes / Paperboards / Hotels / Agri",
        "about": "ITC is one of India's foremost private sector companies with diversified presence in FMCG, Hotels, Paperboards & Packaging, and Agri-business."
    },
    "TATASTEEL": {
        "sector": "Metals & Mining",
        "industry": "Steel Manufacturing & Value-Added Products",
        "about": "Tata Steel is among the top global steel companies with an annual crude steel capacity of 35 million tonnes per annum and integrated operations across India and Europe."
    }
}
