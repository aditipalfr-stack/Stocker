"""
=============================================================================
Stocker V3 Company Registry Seed Metadata
=============================================================================
This module contains bootstrap seed metadata for initial anchor companies
across diverse Indian sectors.

Standardized 10-year financial statements are ingested on demand from Screener.in,
while official corporate filings (Annual Reports, Concall Transcripts, Investor PPTs)
are retrieved from exchange repositories (BSE/NSE/Company IR) for document intelligence
and verification.
=============================================================================
"""

from typing import Dict, Any, List

# Kept for backward-compatibility bootstrapping only; the long-term universe source is company_registry
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

SEED_REGISTRY_COMPANIES: List[Dict[str, Any]] = [
    {
        "symbol": "RELIANCE",
        "company_name": "Reliance Industries Limited",
        "nse_symbol": "RELIANCE",
        "bse_code": "500325",
        "isin": "INE002A01018",
        "exchange": "NSE",
        "sector": "Energy & Conglomerate",
        "industry": "Oil & Gas / Retail / Telecom",
        "aliases": ["Reliance", "RIL", "Jio", "Reliance Industries"],
        "in_universe": True,
        "is_active": True,
        "source": "seed"
    },
    {
        "symbol": "TCS",
        "company_name": "Tata Consultancy Services Limited",
        "nse_symbol": "TCS",
        "bse_code": "532540",
        "isin": "INE467B01029",
        "exchange": "NSE",
        "sector": "Information Technology",
        "industry": "IT Services & Consulting",
        "aliases": ["Tata Consultancy Services", "TCS"],
        "in_universe": True,
        "is_active": True,
        "source": "seed"
    },
    {
        "symbol": "INFY",
        "company_name": "Infosys Limited",
        "nse_symbol": "INFY",
        "bse_code": "500209",
        "isin": "INE009A01021",
        "exchange": "NSE",
        "sector": "Information Technology",
        "industry": "IT Services & Cloud Digital Transformation",
        "aliases": ["Infosys", "INFY"],
        "in_universe": True,
        "is_active": True,
        "source": "seed"
    },
    {
        "symbol": "LT",
        "company_name": "Larsen & Toubro Limited",
        "nse_symbol": "LT",
        "bse_code": "500510",
        "isin": "INE018A01030",
        "exchange": "NSE",
        "sector": "Infrastructure & Engineering",
        "industry": "EPC Projects / Heavy Engineering / Defense",
        "aliases": ["Larsen & Toubro", "L&T", "LT"],
        "in_universe": True,
        "is_active": True,
        "source": "seed"
    },
    {
        "symbol": "HDFCBANK",
        "company_name": "HDFC Bank Limited",
        "nse_symbol": "HDFCBANK",
        "bse_code": "500180",
        "isin": "INE040A01034",
        "exchange": "NSE",
        "sector": "Banking & Financial Services",
        "industry": "Private Sector Bank",
        "aliases": ["HDFC Bank", "HDFC"],
        "in_universe": True,
        "is_active": True,
        "source": "seed"
    },
    {
        "symbol": "ICICIBANK",
        "company_name": "ICICI Bank Limited",
        "nse_symbol": "ICICIBANK",
        "bse_code": "532174",
        "isin": "INE090A01021",
        "exchange": "NSE",
        "sector": "Banking & Financial Services",
        "industry": "Private Sector Bank",
        "aliases": ["ICICI Bank", "ICICI"],
        "in_universe": True,
        "is_active": True,
        "source": "seed"
    },
    {
        "symbol": "TATAMOTORS",
        "company_name": "Tata Motors Passenger Vehicles Limited",
        "nse_symbol": "TATAMOTORS",
        "bse_code": "500570",
        "isin": "INE155A01022",
        "exchange": "NSE",
        "sector": "Automobile",
        "industry": "Commercial Vehicles / Passenger Vehicles / EV / JLR",
        "aliases": ["Tata Motors", "TMPV", "TMCV", "JLR"],
        "in_universe": True,
        "is_active": True,
        "source": "seed"
    },
    {
        "symbol": "HINDUNILVR",
        "company_name": "Hindustan Unilever Limited",
        "nse_symbol": "HINDUNILVR",
        "bse_code": "500696",
        "isin": "INE030A01027",
        "exchange": "NSE",
        "sector": "Consumer Goods / FMCG",
        "industry": "Home Care / Beauty & Personal Care / Foods",
        "aliases": ["Hindustan Unilever", "HUL", "HINDUNILVR"],
        "in_universe": True,
        "is_active": True,
        "source": "seed"
    },
    {
        "symbol": "ITC",
        "company_name": "ITC Limited",
        "nse_symbol": "ITC",
        "bse_code": "500875",
        "isin": "INE154A01025",
        "exchange": "NSE",
        "sector": "Consumer Goods / FMCG",
        "industry": "FMCG / Cigarettes / Paperboards / Hotels / Agri",
        "aliases": ["ITC Limited", "ITC"],
        "in_universe": True,
        "is_active": True,
        "source": "seed"
    },
    {
        "symbol": "TATASTEEL",
        "company_name": "Tata Steel Limited",
        "nse_symbol": "TATASTEEL",
        "bse_code": "500470",
        "isin": "INE081A01020",
        "exchange": "NSE",
        "sector": "Metals & Mining",
        "industry": "Steel Manufacturing & Value-Added Products",
        "aliases": ["Tata Steel", "TISCO"],
        "in_universe": True,
        "is_active": True,
        "source": "seed"
    }
]
