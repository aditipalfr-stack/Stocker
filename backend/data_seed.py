from typing import Dict, List, Any
from models import (
    KeyRatios, FinancialStatement, FinancialRow,
    ConcallInsight, AnnualReportInsight, DocumentLinks
)

SEED_STOCKS: Dict[str, Dict[str, Any]] = {
    "RELIANCE": {
        "symbol": "RELIANCE",
        "name": "Reliance Industries Ltd",
        "sector": "Energy & Conglomerate",
        "industry": "Oil & Gas / Retail / Telecom",
        "about": "Reliance Industries Limited is a Fortune 500 company and the largest private sector corporation in India. Its businesses span hydrocarbon exploration and production, petroleum refining and marketing, petrochemicals, retail, digital services (Jio), and new energy.",
        "ratios": KeyRatios(
            market_cap_cr=1980000.0,
            current_price=2920.0,
            high_low="3217 / 2220",
            stock_pe=28.4,
            book_value=1140.0,
            dividend_yield_pct=0.35,
            roce_pct=10.2,
            roe_pct=9.8,
            face_value=10.0,
            industry_pe=24.5,
            debt_to_equity=0.42,
            interest_coverage=7.1,
            fcf_yield_pct=2.8,
            sales_growth_3yr_cagr=15.4,
            profit_growth_3yr_cagr=11.2
        ),
        "quarters": FinancialStatement(
            periods=["Dec 2022", "Mar 2023", "Jun 2023", "Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024"],
            rows=[
                FinancialRow(metric="Sales", values={"Dec 2022": 217164, "Mar 2023": 212949, "Jun 2023": 207559, "Sep 2023": 231886, "Dec 2023": 225086, "Mar 2024": 236533, "Jun 2024": 231784, "Sep 2024": 231535, "Dec 2024": 242000}),
                FinancialRow(metric="Expenses", values={"Dec 2022": 181924, "Mar 2023": 174507, "Jun 2023": 169460, "Sep 2023": 191001, "Dec 2023": 184436, "Mar 2024": 193988, "Jun 2024": 193020, "Sep 2024": 192500, "Dec 2024": 199500}),
                FinancialRow(metric="Operating Profit", values={"Dec 2022": 35240, "Mar 2023": 38442, "Jun 2023": 38099, "Sep 2023": 40885, "Dec 2023": 40650, "Mar 2024": 42545, "Jun 2024": 38764, "Sep 2024": 39035, "Dec 2024": 42500}),
                FinancialRow(metric="OPM %", values={"Dec 2022": 16.2, "Mar 2023": 18.1, "Jun 2023": 18.4, "Sep 2023": 17.6, "Dec 2023": 18.1, "Mar 2024": 18.0, "Jun 2024": 16.7, "Sep 2024": 16.9, "Dec 2024": 17.6}),
                FinancialRow(metric="Other Income", values={"Dec 2022": 3147, "Mar 2023": 2919, "Jun 2023": 3814, "Sep 2023": 3842, "Dec 2023": 3762, "Mar 2024": 4353, "Jun 2024": 3965, "Sep 2024": 4120, "Dec 2024": 4300}),
                FinancialRow(metric="Interest", values={"Dec 2022": 5201, "Mar 2023": 5819, "Jun 2023": 5837, "Sep 2023": 5731, "Dec 2023": 5794, "Mar 2024": 5761, "Jun 2024": 5910, "Sep 2024": 6020, "Dec 2024": 5950}),
                FinancialRow(metric="Depreciation", values={"Dec 2022": 10187, "Mar 2023": 11456, "Jun 2023": 11775, "Sep 2023": 12581, "Dec 2023": 12903, "Mar 2024": 13569, "Jun 2024": 13596, "Sep 2024": 13750, "Dec 2024": 14100}),
                FinancialRow(metric="Profit before tax", values={"Dec 2022": 22999, "Mar 2023": 24086, "Jun 2023": 24301, "Sep 2023": 26415, "Dec 2023": 25715, "Mar 2024": 27568, "Jun 2024": 23223, "Sep 2024": 23385, "Dec 2024": 26750}),
                FinancialRow(metric="Tax %", values={"Dec 2022": 23.0, "Mar 2023": 20.0, "Jun 2023": 25.0, "Sep 2023": 25.0, "Dec 2023": 24.0, "Mar 2024": 24.0, "Jun 2024": 25.0, "Sep 2024": 25.0, "Dec 2024": 24.0}),
                FinancialRow(metric="Net Profit", values={"Dec 2022": 17706, "Mar 2023": 21327, "Jun 2023": 18258, "Sep 2023": 19878, "Dec 2023": 19641, "Mar 2024": 21243, "Jun 2024": 17448, "Sep 2024": 19101, "Dec 2024": 20850}),
                FinancialRow(metric="EPS in Rs", values={"Dec 2022": 23.3, "Mar 2023": 28.5, "Jun 2023": 23.7, "Sep 2023": 25.8, "Dec 2023": 25.5, "Mar 2024": 27.6, "Jun 2024": 22.8, "Sep 2024": 24.9, "Dec 2024": 27.1})
            ]
        ),
        "profit_loss": FinancialStatement(
            periods=["Mar 2017", "Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "TTM"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2017": 305382, "Mar 2018": 391677, "Mar 2019": 569209, "Mar 2020": 596679, "Mar 2021": 466924, "Mar 2022": 700109, "Mar 2023": 877835, "Mar 2024": 899022, "TTM": 936852}),
                FinancialRow(metric="Expenses", values={"Mar 2017": 259129, "Mar 2018": 327481, "Mar 2019": 485038, "Mar 2020": 508466, "Mar 2021": 386178, "Mar 2022": 589578, "Mar 2023": 734994, "Mar 2024": 750918, "TTM": 778000}),
                FinancialRow(metric="Operating Profit", values={"Mar 2017": 46253, "Mar 2018": 64196, "Mar 2019": 84171, "Mar 2020": 88213, "Mar 2021": 80746, "Mar 2022": 110531, "Mar 2023": 142841, "Mar 2024": 148104, "TTM": 158852}),
                FinancialRow(metric="OPM %", values={"Mar 2017": 15.1, "Mar 2018": 16.4, "Mar 2019": 14.8, "Mar 2020": 14.8, "Mar 2021": 17.3, "Mar 2022": 15.8, "Mar 2023": 16.3, "Mar 2024": 16.5, "TTM": 17.0}),
                FinancialRow(metric="Other Income", values={"Mar 2017": 8704, "Mar 2018": 8862, "Mar 2019": 8386, "Mar 2020": 8498, "Mar 2021": 14595, "Mar 2022": 13915, "Mar 2023": 11776, "Mar 2024": 15762, "TTM": 16700}),
                FinancialRow(metric="Interest", values={"Mar 2017": 3849, "Mar 2018": 8052, "Mar 2019": 16495, "Mar 2020": 22027, "Mar 2021": 21189, "Mar 2022": 14584, "Mar 2023": 19571, "Mar 2024": 23293, "TTM": 23600}),
                FinancialRow(metric="Depreciation", values={"Mar 2017": 11646, "Mar 2018": 16706, "Mar 2019": 20934, "Mar 2020": 22203, "Mar 2021": 26572, "Mar 2022": 29797, "Mar 2023": 40303, "Mar 2024": 50832, "TTM": 54500}),
                FinancialRow(metric="Profit before tax", values={"Mar 2017": 39462, "Mar 2018": 48300, "Mar 2019": 55128, "Mar 2020": 52481, "Mar 2021": 47580, "Mar 2022": 80065, "Mar 2023": 94743, "Mar 2024": 89741, "TTM": 97452}),
                FinancialRow(metric="Tax %", values={"Mar 2017": 24.0, "Mar 2018": 25.0, "Mar 2019": 28.0, "Mar 2020": 25.0, "Mar 2021": 0.0, "Mar 2022": 15.0, "Mar 2023": 22.0, "Mar 2024": 23.0, "TTM": 24.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2017": 29833, "Mar 2018": 36025, "Mar 2019": 39588, "Mar 2020": 39354, "Mar 2021": 49128, "Mar 2022": 67564, "Mar 2023": 73670, "Mar 2024": 69621, "TTM": 78640}),
                FinancialRow(metric="EPS in Rs", values={"Mar 2017": 46.0, "Mar 2018": 55.6, "Mar 2019": 61.1, "Mar 2020": 60.7, "Mar 2021": 75.8, "Mar 2022": 99.8, "Mar 2023": 98.7, "Mar 2024": 94.2, "TTM": 102.8})
            ]
        ),
        "balance_sheet": FinancialStatement(
            periods=["Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "Sep 2024"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2018": 5922, "Mar 2019": 5926, "Mar 2020": 6339, "Mar 2021": 6445, "Mar 2022": 6765, "Mar 2023": 6766, "Mar 2024": 6766, "Sep 2024": 6766}),
                FinancialRow(metric="Reserves", values={"Mar 2018": 287584, "Mar 2019": 381186, "Mar 2020": 446992, "Mar 2021": 693727, "Mar 2022": 772720, "Mar 2023": 708107, "Mar 2024": 786470, "Sep 2024": 820000}),
                FinancialRow(metric="Borrowings", values={"Mar 2018": 218763, "Mar 2019": 287505, "Mar 2020": 336294, "Mar 2021": 251811, "Mar 2022": 266305, "Mar 2023": 313939, "Mar 2024": 324687, "Sep 2024": 330000}),
                FinancialRow(metric="Other Liabilities", values={"Mar 2018": 104085, "Mar 2019": 148464, "Mar 2020": 175949, "Mar 2021": 154674, "Mar 2022": 214588, "Mar 2023": 255280, "Mar 2024": 272449, "Sep 2024": 280000}),
                FinancialRow(metric="Total Liabilities", values={"Mar 2018": 616354, "Mar 2019": 823081, "Mar 2020": 965574, "Mar 2021": 1106657, "Mar 2022": 1260378, "Mar 2023": 1284092, "Mar 2024": 1390372, "Sep 2024": 1436766}),
                FinancialRow(metric="Fixed Assets", values={"Mar 2018": 398684, "Mar 2019": 386375, "Mar 2020": 489728, "Mar 2021": 530467, "Mar 2022": 614050, "Mar 2023": 699894, "Mar 2024": 765410, "Sep 2024": 795000}),
                FinancialRow(metric="CWIP", values={"Mar 2018": 166949, "Mar 2019": 179463, "Mar 2020": 109106, "Mar 2021": 125953, "Mar 2022": 170987, "Mar 2023": 131969, "Mar 2024": 147500, "Sep 2024": 142000}),
                FinancialRow(metric="Investments", values={"Mar 2018": 82862, "Mar 2019": 164612, "Mar 2020": 203852, "Mar 2021": 212382, "Mar 2022": 239019, "Mar 2023": 214702, "Mar 2024": 222180, "Sep 2024": 230000}),
                FinancialRow(metric="Other Assets", values={"Mar 2018": 134808, "Mar 2019": 92631, "Mar 2020": 162888, "Mar 2021": 237855, "Mar 2022": 236322, "Mar 2023": 237527, "Mar 2024": 255282, "Sep 2024": 269766}),
                FinancialRow(metric="Total Assets", values={"Mar 2018": 616354, "Mar 2019": 823081, "Mar 2020": 965574, "Mar 2021": 1106657, "Mar 2022": 1260378, "Mar 2023": 1284092, "Mar 2024": 1390372, "Sep 2024": 1436766})
            ]
        ),
        "cash_flow": FinancialStatement(
            periods=["Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2018": 71146, "Mar 2019": 42346, "Mar 2020": 94877, "Mar 2021": 26185, "Mar 2022": 110654, "Mar 2023": 115049, "Mar 2024": 145239}),
                FinancialRow(metric="Cash from Investing Activity", values={"Mar 2018": -68710, "Mar 2019": -94435, "Mar 2020": -72545, "Mar 2021": -142416, "Mar 2022": -110056, "Mar 2023": -92911, "Mar 2024": -112450}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2018": 65000, "Mar 2019": 85000, "Mar 2020": 68000, "Mar 2021": 95000, "Mar 2022": 105000, "Mar 2023": 88000, "Mar 2024": 98000}),
                FinancialRow(metric="Cash from Financing Activity", values={"Mar 2018": -3431, "Mar 2019": 58316, "Mar 2020": -1984, "Mar 2021": 118465, "Mar 2022": 1045, "Mar 2023": -16987, "Mar 2024": -31250}),
                FinancialRow(metric="Net Cash Flow", values={"Mar 2018": -995, "Mar 2019": 6227, "Mar 2020": 20348, "Mar 2021": 2234, "Mar 2022": 1643, "Mar 2023": 5151, "Mar 2024": 1539})
            ]
        ),
        "concall_insights": [
            ConcallInsight(
                period="Q3 FY25 (Dec 2024)",
                transcript_url="https://www.screener.in/company/RELIANCE/consolidated/#documents",
                presentation_url="https://www.screener.in/company/RELIANCE/consolidated/#documents",
                cfo_and_fcf_analysis="Cash flow from operations reached Rs 38,400 Cr in Q3, backed by strong working capital recovery in Retail and steady upstream realizations. Free Cash Flow conversion improved to 64% of EBITDA as 5G network rollout peak capex concluded, tapering total quarterly capex towards Rs 24,000 Cr.",
                demand_drivers=[
                    "Jio ARPU rose to Rs 195.1 (+7.4% QoQ) following telecom tariff hikes with net subscriber additions of 11.2M.",
                    "Retail footfalls expanded 16% YoY with grocery and consumer electronics recording festive momentum.",
                    "Oil-to-Chemicals (O2C) domestic fuel consumption maintained steady 6% volume growth despite global refining margin normalization."
                ],
                supply_and_capex=[
                    "Solar PV Giga-factory phase 1 (5GW) on track for commissioning by early FY26 in Jamnagar.",
                    "5G PAN-India standalone coverage completed, allowing capex moderation by 25-30% over FY26.",
                    "Petchem capacity expansion for PVC and specialized polymers advancing with CWIP capitalization scheduled for FY26-27."
                ],
                management_guidance="Management guided for low-double-digit EBITDA growth in FY26 led by full-year impact of telecom tariffs and Retail margin expansion. Net debt reduction remains top capital allocation priority.",
                risks_and_headwinds=[
                    "Singapore Gross Refining Margins (GRMs) volatility and petchem margin downcycle in Asia.",
                    "Consumer discretionary demand softness in high-end fashion and lifestyle retail."
                ],
                analyst_sentiment="Constructive - Capex moderation will drive significant FCF expansion from FY26 onwards."
            )
        ],
        "annual_report_insights": [
            AnnualReportInsight(
                year="FY 2024",
                report_url="https://www.screener.in/company/RELIANCE/consolidated/#documents",
                cfo_fcf_performance="CFO crossed record Rs 145,239 Cr (108% of EBITDA). Net capex was Rs 98,000 Cr, yielding positive Free Cash Flow of Rs 47,239 Cr.",
                capex_cwip_summary="CWIP stood at Rs 147,500 Cr primarily comprising New Energy Giga-complexes, 5G enterprise infrastructure, and retail fulfillment hubs.",
                strategic_priorities=[
                    "Scaling New Energy ecosystem (Solar, Green Hydrogen, Energy Storage).",
                    "Monetizing 5G through JioAirFiber and 5G enterprise cloud offerings.",
                    "Expanding omni-channel grocery and private label penetration."
                ],
                forensic_checklist={
                    "promoter_pledge": "0.0% (Zero pledge)",
                    "auditor_qualification": "Unmodified / Clean Audit Report by Deloitte and S R B C & CO",
                    "related_party_transactions": "Standard arms-length operating transactions with JVs",
                    "contingent_liabilities": "Within manageable threshold (<8% of net worth)"
                }
            )
        ],
        "documents": DocumentLinks(
            annual_reports=[
                {"name": "Annual Report FY24", "url": "https://www.screener.in/company/RELIANCE/consolidated/#documents"},
                {"name": "Annual Report FY23", "url": "https://www.screener.in/company/RELIANCE/consolidated/#documents"}
            ],
            concalls=[
                {"name": "Q3 FY25 Earnings Call Transcript", "url": "https://www.screener.in/company/RELIANCE/consolidated/#documents"},
                {"name": "Q2 FY25 Earnings Call Transcript", "url": "https://www.screener.in/company/RELIANCE/consolidated/#documents"}
            ],
            presentations=[
                {"name": "Q3 FY25 Investor Presentation", "url": "https://www.screener.in/company/RELIANCE/consolidated/#documents"},
                {"name": "Q2 FY25 Investor Presentation", "url": "https://www.screener.in/company/RELIANCE/consolidated/#documents"}
            ]
        )
    },
    "TCS": {
        "symbol": "TCS",
        "name": "Tata Consultancy Services Ltd",
        "sector": "Information Technology",
        "industry": "IT Services & Consulting",
        "about": "Tata Consultancy Services is an IT services, consulting and business solutions organization that has been partnering with many of the world's largest businesses in their transformation journeys for over 55 years.",
        "ratios": KeyRatios(
            market_cap_cr=1460000.0,
            current_price=4020.0,
            high_low="4585 / 3313",
            stock_pe=29.2,
            book_value=275.0,
            dividend_yield_pct=1.85,
            roce_pct=62.4,
            roe_pct=50.8,
            face_value=1.0,
            industry_pe=30.1,
            debt_to_equity=0.08,
            interest_coverage=65.0,
            fcf_yield_pct=3.4,
            sales_growth_3yr_cagr=12.8,
            profit_growth_3yr_cagr=10.5
        ),
        "quarters": FinancialStatement(
            periods=["Dec 2022", "Mar 2023", "Jun 2023", "Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024"],
            rows=[
                FinancialRow(metric="Sales", values={"Dec 2022": 58229, "Mar 2023": 59162, "Jun 2023": 59381, "Sep 2023": 59692, "Dec 2023": 60583, "Mar 2024": 61237, "Jun 2024": 62613, "Sep 2024": 64259, "Dec 2024": 64800}),
                FinancialRow(metric="Expenses", values={"Dec 2022": 42721, "Mar 2023": 43414, "Jun 2023": 44460, "Sep 2023": 44215, "Dec 2023": 44747, "Mar 2024": 44791, "Jun 2024": 46522, "Sep 2024": 47716, "Dec 2024": 48100}),
                FinancialRow(metric="Operating Profit", values={"Dec 2022": 15508, "Mar 2023": 15748, "Jun 2023": 14921, "Sep 2023": 15477, "Dec 2023": 15836, "Mar 2024": 16446, "Jun 2024": 16091, "Sep 2024": 16543, "Dec 2024": 16700}),
                FinancialRow(metric="OPM %", values={"Dec 2022": 26.6, "Mar 2023": 26.6, "Jun 2023": 25.1, "Sep 2023": 25.9, "Dec 2023": 26.1, "Mar 2024": 26.9, "Jun 2024": 25.7, "Sep 2024": 25.7, "Dec 2024": 25.8}),
                FinancialRow(metric="Other Income", values={"Dec 2022": 1445, "Mar 2023": 929, "Jun 2023": 1332, "Sep 2023": 1287, "Dec 2023": 1555, "Mar 2024": 1157, "Jun 2024": 1420, "Sep 2024": 1380, "Dec 2024": 1450}),
                FinancialRow(metric="Interest", values={"Dec 2022": 158, "Mar 2023": 242, "Jun 2023": 194, "Sep 2023": 204, "Dec 2023": 208, "Mar 2024": 173, "Jun 2024": 200, "Sep 2024": 210, "Dec 2024": 205}),
                FinancialRow(metric="Depreciation", values={"Dec 2022": 1291, "Mar 2023": 1308, "Jun 2023": 1243, "Sep 2023": 1248, "Dec 2023": 1246, "Mar 2024": 1249, "Jun 2024": 1250, "Sep 2024": 1260, "Dec 2024": 1270}),
                FinancialRow(metric="Profit before tax", values={"Dec 2022": 15504, "Mar 2023": 15127, "Jun 2023": 14816, "Sep 2023": 15312, "Dec 2023": 15937, "Mar 2024": 16181, "Jun 2024": 16061, "Sep 2024": 16453, "Dec 2024": 16675}),
                FinancialRow(metric="Tax %", values={"Dec 2022": 29.0, "Mar 2023": 25.0, "Jun 2023": 25.0, "Sep 2023": 26.0, "Dec 2023": 26.0, "Mar 2024": 26.0, "Jun 2024": 25.0, "Sep 2024": 26.0, "Dec 2024": 26.0}),
                FinancialRow(metric="Net Profit", values={"Dec 2022": 10883, "Mar 2023": 11436, "Jun 2023": 11120, "Sep 2023": 11380, "Dec 2023": 11774, "Mar 2024": 12502, "Jun 2024": 12105, "Sep 2024": 12040, "Dec 2024": 12340}),
                FinancialRow(metric="EPS in Rs", values={"Dec 2022": 29.7, "Mar 2023": 31.3, "Jun 2023": 30.4, "Sep 2023": 31.1, "Dec 2023": 32.2, "Mar 2024": 34.2, "Jun 2024": 33.1, "Sep 2024": 32.9, "Dec 2024": 33.8})
            ]
        ),
        "profit_loss": FinancialStatement(
            periods=["Mar 2017", "Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "TTM"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2017": 117966, "Mar 2018": 123104, "Mar 2019": 146463, "Mar 2020": 156949, "Mar 2021": 164177, "Mar 2022": 191754, "Mar 2023": 225458, "Mar 2024": 240893, "TTM": 252909}),
                FinancialRow(metric="Expenses", values={"Mar 2017": 85656, "Mar 2018": 90588, "Mar 2019": 106957, "Mar 2020": 114840, "Mar 2021": 117630, "Mar 2022": 138697, "Mar 2023": 166298, "Mar 2024": 176860, "TTM": 185129}),
                FinancialRow(metric="Operating Profit", values={"Mar 2017": 32310, "Mar 2018": 32516, "Mar 2019": 39506, "Mar 2020": 42109, "Mar 2021": 46547, "Mar 2022": 53057, "Mar 2023": 59160, "Mar 2024": 64033, "TTM": 67780}),
                FinancialRow(metric="OPM %", values={"Mar 2017": 27.4, "Mar 2018": 26.4, "Mar 2019": 27.0, "Mar 2020": 26.8, "Mar 2021": 28.4, "Mar 2022": 27.7, "Mar 2023": 26.2, "Mar 2024": 26.6, "TTM": 26.8}),
                FinancialRow(metric="Other Income", values={"Mar 2017": 4221, "Mar 2018": 3640, "Mar 2019": 4311, "Mar 2020": 4571, "Mar 2021": 3134, "Mar 2022": 4018, "Mar 2023": 3449, "Mar 2024": 4867, "TTM": 5407}),
                FinancialRow(metric="Interest", values={"Mar 2017": 32, "Mar 2018": 52, "Mar 2019": 198, "Mar 2020": 924, "Mar 2021": 637, "Mar 2022": 784, "Mar 2023": 779, "Mar 2024": 779, "TTM": 820}),
                FinancialRow(metric="Depreciation", values={"Mar 2017": 1987, "Mar 2018": 2014, "Mar 2019": 2056, "Mar 2020": 3529, "Mar 2021": 4065, "Mar 2022": 4604, "Mar 2023": 5022, "Mar 2024": 4986, "TTM": 5026}),
                FinancialRow(metric="Profit before tax", values={"Mar 2017": 34512, "Mar 2018": 34090, "Mar 2019": 41563, "Mar 2020": 42227, "Mar 2021": 44979, "Mar 2022": 51687, "Mar 2023": 56808, "Mar 2024": 63135, "TTM": 67341}),
                FinancialRow(metric="Tax %", values={"Mar 2017": 24.0, "Mar 2018": 24.0, "Mar 2019": 24.0, "Mar 2020": 23.0, "Mar 2021": 26.0, "Mar 2022": 26.0, "Mar 2023": 26.0, "Mar 2024": 26.0, "TTM": 26.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2017": 26357, "Mar 2018": 25880, "Mar 2019": 31562, "Mar 2020": 32447, "Mar 2021": 32562, "Mar 2022": 38449, "Mar 2023": 42303, "Mar 2024": 46099, "TTM": 49987}),
                FinancialRow(metric="EPS in Rs", values={"Mar 2017": 67.0, "Mar 2018": 67.6, "Mar 2019": 84.1, "Mar 2020": 86.5, "Mar 2021": 88.0, "Mar 2022": 105.0, "Mar 2023": 115.6, "Mar 2024": 126.8, "TTM": 137.5})
            ]
        ),
        "balance_sheet": FinancialStatement(
            periods=["Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2018": 191, "Mar 2019": 375, "Mar 2020": 375, "Mar 2021": 370, "Mar 2022": 366, "Mar 2023": 366, "Mar 2024": 362}),
                FinancialRow(metric="Reserves", values={"Mar 2018": 87349, "Mar 2019": 92257, "Mar 2020": 85800, "Mar 2021": 88301, "Mar 2022": 91873, "Mar 2023": 92398, "Mar 2024": 99740}),
                FinancialRow(metric="Borrowings", values={"Mar 2018": 247, "Mar 2019": 64, "Mar 2020": 8174, "Mar 2021": 7795, "Mar 2022": 7818, "Mar 2023": 7824, "Mar 2024": 8200}),
                FinancialRow(metric="Other Liabilities", values={"Mar 2018": 24206, "Mar 2019": 26978, "Mar 2020": 26365, "Mar 2021": 37703, "Mar 2022": 44439, "Mar 2023": 44675, "Mar 2024": 46520}),
                FinancialRow(metric="Total Liabilities", values={"Mar 2018": 111993, "Mar 2019": 119674, "Mar 2020": 120714, "Mar 2021": 134169, "Mar 2022": 144496, "Mar 2023": 145263, "Mar 2024": 154822}),
                FinancialRow(metric="Fixed Assets", values={"Mar 2018": 13627, "Mar 2019": 14216, "Mar 2020": 23671, "Mar 2021": 24213, "Mar 2022": 24653, "Mar 2023": 24500, "Mar 2024": 25100}),
                FinancialRow(metric="CWIP", values={"Mar 2018": 2043, "Mar 2019": 1144, "Mar 2020": 1056, "Mar 2021": 1324, "Mar 2022": 1420, "Mar 2023": 1560, "Mar 2024": 1640}),
                FinancialRow(metric="Investments", values={"Mar 2018": 41887, "Mar 2019": 33904, "Mar 2020": 34960, "Mar 2021": 38489, "Mar 2022": 41250, "Mar 2023": 43500, "Mar 2024": 46800}),
                FinancialRow(metric="Other Assets", values={"Mar 2018": 54436, "Mar 2019": 70410, "Mar 2020": 61027, "Mar 2021": 70143, "Mar 2022": 77173, "Mar 2023": 75703, "Mar 2024": 81282}),
                FinancialRow(metric="Total Assets", values={"Mar 2018": 111993, "Mar 2019": 119674, "Mar 2020": 120714, "Mar 2021": 134169, "Mar 2022": 144496, "Mar 2023": 145263, "Mar 2024": 154822})
            ]
        ),
        "cash_flow": FinancialStatement(
            periods=["Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2018": 28161, "Mar 2019": 28593, "Mar 2020": 32369, "Mar 2021": 38802, "Mar 2022": 39949, "Mar 2023": 41965, "Mar 2024": 49100}),
                FinancialRow(metric="Cash from Investing Activity", values={"Mar 2018": 2235, "Mar 2019": 4440, "Mar 2020": -4493, "Mar 2021": -4814, "Mar 2022": -3890, "Mar 2023": -4120, "Mar 2024": -4600}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2018": 2500, "Mar 2019": 2600, "Mar 2020": 3000, "Mar 2021": 3200, "Mar 2022": 3100, "Mar 2023": 3300, "Mar 2024": 3400}),
                FinancialRow(metric="Cash from Financing Activity", values={"Mar 2018": -30298, "Mar 2019": -33160, "Mar 2020": -27429, "Mar 2021": -33350, "Mar 2022": -36400, "Mar 2023": -37800, "Mar 2024": -44200}),
                FinancialRow(metric="Net Cash Flow", values={"Mar 2018": 98, "Mar 2019": -127, "Mar 2020": 447, "Mar 2021": 638, "Mar 2022": -341, "Mar 2023": 45, "Mar 2024": 300})
            ]
        ),
        "concall_insights": [
            ConcallInsight(
                period="Q3 FY25 (Dec 2024)",
                transcript_url="https://www.screener.in/company/TCS/consolidated/#documents",
                presentation_url="https://www.screener.in/company/TCS/consolidated/#documents",
                cfo_and_fcf_analysis="Cash conversion remained pristine at 104% of Net Profit with CFO of Rs 12,850 Cr. FCF for the quarter stood at Rs 11,950 Cr, supporting continuing 80%+ dividend payout policy.",
                demand_drivers=[
                    "Deal TCV stood robust at $8.6B, with major mega-deal renewals in BFSI and manufacturing.",
                    "GenAI and Cloud transformation engagements doubled in pipeline, with over 350+ generative AI PoCs moving to enterprise production.",
                    "North America stabilized (+1.2% QoQ) while UK and Continental Europe posted resilient mid-single digit growth."
                ],
                supply_and_capex=[
                    "Attrition down to industry-low 12.1% LTM, reducing reliance on expensive subcontractors.",
                    "Utilization improved to 85.5% excluding trainees.",
                    "Minimal capex required (~1.5% of sales) ensuring high ROIC of >55%."
                ],
                management_guidance="Management reiterated confidence in returning to double-digit constant-currency revenue growth in FY26 driven by BFSI spend revival and enterprise cost-optimization mega-deals.",
                risks_and_headwinds=[
                    "Discretionary tech spend in European retail/telecom remains cautious.",
                    "Higher wage hike cycles scheduled in Q1 FY26."
                ],
                analyst_sentiment="Bullish - Gold standard in capital allocation, pristine cash flow, and best-in-class profitability."
            )
        ],
        "annual_report_insights": [
            AnnualReportInsight(
                year="FY 2024",
                report_url="https://www.screener.in/company/TCS/consolidated/#documents",
                cfo_fcf_performance="CFO reached Rs 49,100 Cr (106.5% of PAT). FCF was Rs 45,700 Cr, of which Rs 44,200 Cr was returned to shareholders via dividends and buybacks.",
                capex_cwip_summary="Capex of Rs 3,400 Cr focused on AI labs, data center modernization, and campus expansions.",
                strategic_priorities=[
                    "Embedding AI across the full SDLC and client service delivery.",
                    "Deepening domain-specific consulting in BFSI, Life Sciences, and Aerospace.",
                    "Expanding delivery centers in tier-2/3 Indian cities and Latin America."
                ],
                forensic_checklist={
                    "promoter_pledge": "0.0% (Zero pledge)",
                    "auditor_qualification": "Unmodified / Clean Audit Report by B S R & Co.",
                    "related_party_transactions": "Arms-length Tata group corporate transactions",
                    "contingent_liabilities": "Negligible (<1.5% of net worth)"
                }
            )
        ],
        "documents": DocumentLinks(
            annual_reports=[
                {"name": "Annual Report FY24", "url": "https://www.screener.in/company/TCS/consolidated/#documents"},
                {"name": "Annual Report FY23", "url": "https://www.screener.in/company/TCS/consolidated/#documents"}
            ],
            concalls=[
                {"name": "Q3 FY25 Earnings Call Transcript", "url": "https://www.screener.in/company/TCS/consolidated/#documents"}
            ],
            presentations=[
                {"name": "Q3 FY25 Investor Presentation", "url": "https://www.screener.in/company/TCS/consolidated/#documents"}
            ]
        )
    },
    "BHARTIARTL": {
        "symbol": "BHARTIARTL",
        "name": "Bharti Airtel Ltd",
        "sector": "Telecommunications",
        "industry": "Telecom Services / 5G / Cloud",
        "about": "Bharti Airtel is a global communications solutions provider with over 500 Mn customers across 17 countries in South Asia and Africa. In India, it offers 4G/5G mobile, fixed broadband, DTH, enterprise connectivity, and digital payments.",
        "ratios": KeyRatios(
            market_cap_cr=1080000.0,
            current_price=1780.0,
            high_low="1920 / 1150",
            stock_pe=42.5,
            book_value=195.0,
            dividend_yield_pct=0.55,
            roce_pct=16.8,
            roe_pct=21.2,
            face_value=5.0,
            industry_pe=38.0,
            debt_to_equity=1.2,
            interest_coverage=4.8,
            fcf_yield_pct=4.1,
            sales_growth_3yr_cagr=17.2,
            profit_growth_3yr_cagr=48.5
        ),
        "quarters": FinancialStatement(
            periods=["Dec 2022", "Mar 2023", "Jun 2023", "Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024"],
            rows=[
                FinancialRow(metric="Sales", values={"Dec 2022": 35871, "Mar 2023": 36009, "Jun 2023": 37440, "Sep 2023": 37044, "Dec 2023": 37900, "Mar 2024": 37599, "Jun 2024": 38506, "Sep 2024": 41473, "Dec 2024": 43200}),
                FinancialRow(metric="Expenses", values={"Dec 2022": 17822, "Mar 2023": 17565, "Jun 2023": 17799, "Sep 2023": 17469, "Dec 2023": 17926, "Mar 2024": 17965, "Jun 2024": 18560, "Sep 2024": 19680, "Dec 2024": 20100}),
                FinancialRow(metric="Operating Profit", values={"Dec 2022": 18049, "Mar 2023": 18444, "Jun 2023": 19641, "Sep 2023": 19575, "Dec 2023": 19974, "Mar 2024": 19634, "Jun 2024": 19946, "Sep 2024": 21793, "Dec 2024": 23100}),
                FinancialRow(metric="OPM %", values={"Dec 2022": 50.3, "Mar 2023": 51.2, "Jun 2023": 52.5, "Sep 2023": 52.8, "Dec 2023": 52.7, "Mar 2024": 52.2, "Jun 2024": 51.8, "Sep 2024": 52.5, "Dec 2024": 53.5}),
                FinancialRow(metric="Other Income", values={"Dec 2022": 320, "Mar 2023": 215, "Jun 2023": 410, "Sep 2023": 290, "Dec 2023": 340, "Mar 2024": 420, "Jun 2024": 380, "Sep 2024": 410, "Dec 2024": 450}),
                FinancialRow(metric="Interest", values={"Dec 2022": 4541, "Mar 2023": 4725, "Jun 2023": 4980, "Sep 2023": 5120, "Dec 2023": 5190, "Mar 2024": 5240, "Jun 2024": 5150, "Sep 2024": 5050, "Dec 2024": 4950}),
                FinancialRow(metric="Depreciation", values={"Dec 2022": 9298, "Mar 2023": 9350, "Jun 2023": 9710, "Sep 2023": 9950, "Dec 2023": 10120, "Mar 2024": 10320, "Jun 2024": 10350, "Sep 2024": 10480, "Dec 2024": 10600}),
                FinancialRow(metric="Profit before tax", values={"Dec 2022": 4530, "Mar 2023": 4584, "Jun 2023": 5361, "Sep 2023": 4795, "Dec 2023": 5004, "Mar 2024": 4494, "Jun 2024": 4826, "Sep 2024": 6673, "Dec 2024": 8000}),
                FinancialRow(metric="Tax %", values={"Dec 2022": 31.0, "Mar 2023": 33.0, "Jun 2023": 28.0, "Sep 2023": 32.0, "Dec 2023": 29.0, "Mar 2024": 38.0, "Jun 2024": 25.0, "Sep 2024": 27.0, "Dec 2024": 26.0}),
                FinancialRow(metric="Net Profit", values={"Dec 2022": 2153, "Mar 2023": 3006, "Jun 2023": 4160, "Sep 2023": 2093, "Dec 2023": 2876, "Mar 2024": 2072, "Jun 2024": 4160, "Sep 2024": 4153, "Dec 2024": 5600}),
                FinancialRow(metric="EPS in Rs", values={"Dec 2022": 3.6, "Mar 2023": 5.1, "Jun 2023": 7.0, "Sep 2023": 3.5, "Dec 2023": 4.8, "Mar 2024": 3.5, "Jun 2024": 7.0, "Sep 2024": 7.0, "Dec 2024": 9.4})
            ]
        ),
        "profit_loss": FinancialStatement(
            periods=["Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "TTM"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2018": 83688, "Mar 2019": 80780, "Mar 2020": 87539, "Mar 2021": 100616, "Mar 2022": 116547, "Mar 2023": 139145, "Mar 2024": 149982, "TTM": 160778}),
                FinancialRow(metric="Expenses", values={"Mar 2018": 53607, "Mar 2019": 54992, "Mar 2020": 51139, "Mar 2021": 55243, "Mar 2022": 59013, "Mar 2023": 67885, "Mar 2024": 71160, "TTM": 76340}),
                FinancialRow(metric="Operating Profit", values={"Mar 2018": 30081, "Mar 2019": 25788, "Mar 2020": 36400, "Mar 2021": 45373, "Mar 2022": 57534, "Mar 2023": 71260, "Mar 2024": 78822, "TTM": 84438}),
                FinancialRow(metric="OPM %", values={"Mar 2018": 35.9, "Mar 2019": 31.9, "Mar 2020": 41.6, "Mar 2021": 45.1, "Mar 2022": 49.4, "Mar 2023": 51.2, "Mar 2024": 52.6, "TTM": 52.5}),
                FinancialRow(metric="Other Income", values={"Mar 2018": 1582, "Mar 2019": 460, "Mar 2020": 1941, "Mar 2021": 599, "Mar 2022": 546, "Mar 2023": 1020, "Mar 2024": 1460, "TTM": 1650}),
                FinancialRow(metric="Interest", values={"Mar 2018": 8072, "Mar 2019": 9589, "Mar 2020": 13992, "Mar 2021": 15091, "Mar 2022": 16617, "Mar 2023": 19300, "Mar 2024": 20530, "TTM": 20150}),
                FinancialRow(metric="Depreciation", values={"Mar 2018": 19243, "Mar 2019": 21348, "Mar 2020": 27690, "Mar 2021": 29404, "Mar 2022": 33091, "Mar 2023": 36432, "Mar 2024": 39500, "TTM": 41780}),
                FinancialRow(metric="Profit before tax", values={"Mar 2018": 4348, "Mar 2019": -4689, "Mar 2020": -33261, "Mar 2021": 1477, "Mar 2022": 8372, "Mar 2023": 16548, "Mar 2024": 20252, "TTM": 24158}),
                FinancialRow(metric="Tax %", values={"Mar 2018": 60.0, "Mar 2019": -20.0, "Mar 2020": -3.0, "Mar 2021": -27.0, "Mar 2022": 49.0, "Mar 2023": 37.0, "Mar 2024": 32.0, "TTM": 27.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2018": 1099, "Mar 2019": 409, "Mar 2020": -32183, "Mar 2021": -15084, "Mar 2022": 4255, "Mar 2023": 8346, "Mar 2024": 7467, "TTM": 17913}),
                FinancialRow(metric="EPS in Rs", values={"Mar 2018": 2.7, "Mar 2019": 1.0, "Mar 2020": -60.8, "Mar 2021": -27.5, "Mar 2022": 7.5, "Mar 2023": 14.5, "Mar 2024": 12.8, "TTM": 29.8})
            ]
        ),
        "balance_sheet": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "Sep 2024"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2019": 1999, "Mar 2020": 2728, "Mar 2021": 2746, "Mar 2022": 2795, "Mar 2023": 2835, "Mar 2024": 2865, "Sep 2024": 2865}),
                FinancialRow(metric="Reserves", values={"Mar 2019": 69424, "Mar 2020": 74417, "Mar 2021": 56207, "Mar 2022": 63760, "Mar 2023": 74728, "Mar 2024": 82140, "Sep 2024": 94000}),
                FinancialRow(metric="Borrowings", values={"Mar 2019": 125428, "Mar 2020": 148228, "Mar 2021": 158580, "Mar 2022": 170940, "Mar 2023": 213126, "Mar 2024": 204900, "Sep 2024": 195000}),
                FinancialRow(metric="Other Liabilities", values={"Mar 2019": 78378, "Mar 2020": 135118, "Mar 2021": 128362, "Mar 2022": 126130, "Mar 2023": 128450, "Mar 2024": 132600, "Sep 2024": 135000}),
                FinancialRow(metric="Total Liabilities", values={"Mar 2019": 275229, "Mar 2020": 360491, "Mar 2021": 345895, "Mar 2022": 363625, "Mar 2023": 419139, "Mar 2024": 422505, "Sep 2024": 426865}),
                FinancialRow(metric="Fixed Assets", values={"Mar 2019": 143320, "Mar 2020": 215440, "Mar 2021": 217420, "Mar 2022": 234120, "Mar 2023": 285400, "Mar 2024": 298000, "Sep 2024": 305000}),
                FinancialRow(metric="CWIP", values={"Mar 2019": 6512, "Mar 2020": 4650, "Mar 2021": 5120, "Mar 2022": 6890, "Mar 2023": 7520, "Mar 2024": 8200, "Sep 2024": 7400}),
                FinancialRow(metric="Investments", values={"Mar 2019": 15410, "Mar 2020": 26890, "Mar 2021": 24800, "Mar 2022": 28100, "Mar 2023": 31200, "Mar 2024": 34500, "Sep 2024": 36000}),
                FinancialRow(metric="Other Assets", values={"Mar 2019": 109987, "Mar 2020": 113511, "Mar 2021": 98555, "Mar 2022": 94515, "Mar 2023": 95019, "Mar 2024": 81805, "Sep 2024": 78465}),
                FinancialRow(metric="Total Assets", values={"Mar 2019": 275229, "Mar 2020": 360491, "Mar 2021": 345895, "Mar 2022": 363625, "Mar 2023": 419139, "Mar 2024": 422505, "Sep 2024": 426865})
            ]
        ),
        "cash_flow": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2019": 20456, "Mar 2020": 21054, "Mar 2021": 39688, "Mar 2022": 49826, "Mar 2023": 59124, "Mar 2024": 72480}),
                FinancialRow(metric="Cash from Investing Activity", values={"Mar 2019": -27450, "Mar 2020": -24560, "Mar 2021": -28900, "Mar 2022": -32500, "Mar 2023": -38400, "Mar 2024": -36800}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2019": 28000, "Mar 2020": 25000, "Mar 2021": 29000, "Mar 2022": 32000, "Mar 2023": 37500, "Mar 2024": 35000}),
                FinancialRow(metric="Cash from Financing Activity", values={"Mar 2019": 7650, "Mar 2020": 9800, "Mar 2021": -9800, "Mar 2022": -15600, "Mar 2023": -19800, "Mar 2024": -33500}),
                FinancialRow(metric="Net Cash Flow", values={"Mar 2019": 656, "Mar 2020": 6294, "Mar 2021": 988, "Mar 2022": 1726, "Mar 2023": 924, "Mar 2024": 2180})
            ]
        ),
        "concall_insights": [
            ConcallInsight(
                period="Q3 FY25 (Dec 2024)",
                transcript_url="https://www.screener.in/company/BHARTIARTL/consolidated/#documents",
                presentation_url="https://www.screener.in/company/BHARTIARTL/consolidated/#documents",
                cfo_and_fcf_analysis="Cash flow from operations reached Rs 21,500 Cr in the quarter. Free Cash Flow after Capex stood at Rs 12,800 Cr, enabling prepayments of high-cost DoT spectrum liabilities of Rs 8,400 Cr.",
                demand_drivers=[
                    "India Mobile ARPU surged to Rs 233 (+12.5% YoY), on track towards management's medium-term target of Rs 300.",
                    "Postpaid subscriber additions crossed 1.2M in the quarter.",
                    "Homes broadband customer base grew 27% YoY to 8.5M subscribers."
                ],
                supply_and_capex=[
                    "5G capex has peaked; FY26 India mobile capex expected to drop by 20% to under Rs 25,000 Cr.",
                    "Rollout of 4G/5G rural coverage towers nearing completion with 30,000 high-yield sites added."
                ],
                management_guidance="Management guided for sustained operating leverage with incremental EBITDA margins exceeding 65% on future tariff hikes and rapid enterprise 5G monetization.",
                risks_and_headwinds=[
                    "Currency devaluation headwinds in Nigeria and East Africa.",
                    "Higher AGR legal liabilities timeline clarity."
                ],
                analyst_sentiment="High Conviction Bullish - Powerful compounding with ARPU expansion + Capex tapering unlocking massive Free Cash Flow."
            )
        ],
        "annual_report_insights": [
            AnnualReportInsight(
                year="FY 2024",
                report_url="https://www.screener.in/company/BHARTIARTL/consolidated/#documents",
                cfo_fcf_performance="CFO crossed record Rs 72,480 Cr. Net Free cash flow post capex was Rs 37,480 Cr, generating unprecedented cash generation.",
                capex_cwip_summary="Completed 5G deployment across 20,000+ towns; CWIP moderated to Rs 8,200 Cr.",
                strategic_priorities=[
                    "Driving premiumization with Airtel Black convergence packages.",
                    "Scaling B2B Enterprise connectivity, CPaaS, and Airtel Cloud / Nxtra Data Centers.",
                    "Aggressive balance sheet deleveraging to achieve Net Debt/EBITDA < 1.0x."
                ],
                forensic_checklist={
                    "promoter_pledge": "0.0% (Zero pledge)",
                    "auditor_qualification": "Unmodified / Clean Audit Report by Deloitte",
                    "related_party_transactions": "Arms-length tower sharing with Indus Towers",
                    "contingent_liabilities": "Standard telecom regulatory spectrum matters"
                }
            )
        ],
        "documents": DocumentLinks(
            annual_reports=[
                {"name": "Annual Report FY24", "url": "https://www.screener.in/company/BHARTIARTL/consolidated/#documents"},
                {"name": "Annual Report FY23", "url": "https://www.screener.in/company/BHARTIARTL/consolidated/#documents"}
            ],
            concalls=[
                {"name": "Q3 FY25 Earnings Call Transcript", "url": "https://www.screener.in/company/BHARTIARTL/consolidated/#documents"}
            ],
            presentations=[
                {"name": "Q3 FY25 Investor Presentation", "url": "https://www.screener.in/company/BHARTIARTL/consolidated/#documents"}
            ]
        )
    },
    "LT": {
        "symbol": "LT",
        "name": "Larsen & Toubro Ltd",
        "sector": "Infrastructure & Engineering",
        "industry": "EPC Projects / Heavy Engineering / Defense",
        "about": "Larsen & Toubro is an Indian multinational engaged in EPC Projects, Hi-Tech Manufacturing and Services. It operates in over 50 countries worldwide. A strong, customer-focused approach and the constant quest for top-class quality have enabled L&T to attain leadership in major lines of business.",
        "ratios": KeyRatios(
            market_cap_cr=510000.0,
            current_price=3710.0,
            high_low="3948 / 2850",
            stock_pe=34.8,
            book_value=670.0,
            dividend_yield_pct=0.92,
            roce_pct=17.5,
            roe_pct=16.8,
            face_value=2.0,
            industry_pe=32.0,
            debt_to_equity=0.78,
            interest_coverage=6.2,
            fcf_yield_pct=3.1,
            sales_growth_3yr_cagr=19.4,
            profit_growth_3yr_cagr=22.1
        ),
        "quarters": FinancialStatement(
            periods=["Dec 2022", "Mar 2023", "Jun 2023", "Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024"],
            rows=[
                FinancialRow(metric="Sales", values={"Dec 2022": 46390, "Mar 2023": 58335, "Jun 2023": 47882, "Sep 2023": 51024, "Dec 2023": 55128, "Mar 2024": 67079, "Jun 2024": 55120, "Sep 2024": 61555, "Dec 2024": 66200}),
                FinancialRow(metric="Expenses", values={"Dec 2022": 41317, "Mar 2023": 51480, "Jun 2023": 43014, "Sep 2023": 45402, "Dec 2023": 49372, "Mar 2024": 59578, "Jun 2024": 49510, "Sep 2024": 55210, "Dec 2024": 59100}),
                FinancialRow(metric="Operating Profit", values={"Dec 2022": 5073, "Mar 2023": 6855, "Jun 2023": 4868, "Sep 2023": 5622, "Dec 2023": 5756, "Mar 2024": 7501, "Jun 2024": 5610, "Sep 2024": 6345, "Dec 2024": 7100}),
                FinancialRow(metric="OPM %", values={"Dec 2022": 10.9, "Mar 2023": 11.8, "Jun 2023": 10.2, "Sep 2023": 11.0, "Dec 2023": 10.4, "Mar 2024": 11.2, "Jun 2024": 10.2, "Sep 2024": 10.3, "Dec 2024": 10.7}),
                FinancialRow(metric="Other Income", values={"Dec 2022": 745, "Mar 2023": 950, "Jun 2023": 1030, "Sep 2023": 1150, "Dec 2023": 1280, "Mar 2024": 1420, "Jun 2024": 1310, "Sep 2024": 1380, "Dec 2024": 1450}),
                FinancialRow(metric="Interest", values={"Dec 2022": 823, "Mar 2023": 890, "Jun 2023": 920, "Sep 2023": 960, "Dec 2023": 980, "Mar 2024": 1020, "Jun 2024": 990, "Sep 2024": 980, "Dec 2024": 960}),
                FinancialRow(metric="Depreciation", values={"Dec 2022": 832, "Mar 2023": 895, "Jun 2023": 940, "Sep 2023": 960, "Dec 2023": 990, "Mar 2024": 1010, "Jun 2024": 1030, "Sep 2024": 1040, "Dec 2024": 1060}),
                FinancialRow(metric="Profit before tax", values={"Dec 2022": 4163, "Mar 2023": 6020, "Jun 2023": 4038, "Sep 2023": 4852, "Dec 2023": 5066, "Mar 2024": 6891, "Jun 2024": 4900, "Sep 2024": 5705, "Dec 2024": 6530}),
                FinancialRow(metric="Tax %", values={"Dec 2022": 27.0, "Mar 2023": 26.0, "Jun 2023": 25.0, "Sep 2023": 26.0, "Dec 2023": 27.0, "Mar 2024": 25.0, "Jun 2024": 27.0, "Sep 2024": 26.0, "Dec 2024": 26.0}),
                FinancialRow(metric="Net Profit", values={"Dec 2022": 2553, "Mar 2023": 3987, "Jun 2023": 2493, "Sep 2023": 3223, "Dec 2023": 2947, "Mar 2024": 4396, "Jun 2024": 2786, "Sep 2024": 3395, "Dec 2024": 4200}),
                FinancialRow(metric="EPS in Rs", values={"Dec 2022": 18.2, "Mar 2023": 28.4, "Jun 2023": 17.7, "Sep 2023": 22.9, "Dec 2023": 21.0, "Mar 2024": 31.3, "Jun 2024": 19.8, "Sep 2024": 24.2, "Dec 2024": 29.9})
            ]
        ),
        "profit_loss": FinancialStatement(
            periods=["Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "TTM"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2018": 119862, "Mar 2019": 141007, "Mar 2020": 145452, "Mar 2021": 135979, "Mar 2022": 156521, "Mar 2023": 183341, "Mar 2024": 221113, "TTM": 249874}),
                FinancialRow(metric="Expenses", values={"Mar 2018": 106290, "Mar 2019": 124678, "Mar 2020": 129123, "Mar 2021": 120355, "Mar 2022": 138302, "Mar 2023": 162590, "Mar 2024": 197365, "TTM": 223400}),
                FinancialRow(metric="Operating Profit", values={"Mar 2018": 13572, "Mar 2019": 16329, "Mar 2020": 16329, "Mar 2021": 15624, "Mar 2022": 18219, "Mar 2023": 20751, "Mar 2024": 23748, "TTM": 26474}),
                FinancialRow(metric="OPM %", values={"Mar 2018": 11.3, "Mar 2019": 11.6, "Mar 2020": 11.2, "Mar 2021": 11.5, "Mar 2022": 11.6, "Mar 2023": 11.3, "Mar 2024": 10.7, "TTM": 10.6}),
                FinancialRow(metric="Other Income", values={"Mar 2018": 1412, "Mar 2019": 1836, "Mar 2020": 2361, "Mar 2021": 3899, "Mar 2022": 2267, "Mar 2023": 2928, "Mar 2024": 4180, "TTM": 5560}),
                FinancialRow(metric="Interest", values={"Mar 2018": 1538, "Mar 2019": 1803, "Mar 2020": 2797, "Mar 2021": 3913, "Mar 2022": 3125, "Mar 2023": 3209, "Mar 2024": 3880, "TTM": 3950}),
                FinancialRow(metric="Depreciation", values={"Mar 2018": 1928, "Mar 2019": 1923, "Mar 2020": 2462, "Mar 2021": 2904, "Mar 2022": 2948, "Mar 2023": 3502, "Mar 2024": 3930, "TTM": 4140}),
                FinancialRow(metric="Profit before tax", values={"Mar 2018": 11518, "Mar 2019": 14439, "Mar 2020": 13431, "Mar 2021": 12706, "Mar 2022": 14413, "Mar 2023": 16968, "Mar 2024": 20118, "TTM": 23944}),
                FinancialRow(metric="Tax %", values={"Mar 2018": 30.0, "Mar 2019": 31.0, "Mar 2020": 29.0, "Mar 2021": 24.0, "Mar 2022": 26.0, "Mar 2023": 27.0, "Mar 2024": 26.0, "TTM": 26.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2018": 7370, "Mar 2019": 8905, "Mar 2020": 9549, "Mar 2021": 11583, "Mar 2022": 8572, "Mar 2023": 10471, "Mar 2024": 13059, "TTM": 14777}),
                FinancialRow(metric="EPS in Rs", values={"Mar 2018": 52.6, "Mar 2019": 63.5, "Mar 2020": 68.0, "Mar 2021": 82.5, "Mar 2022": 61.0, "Mar 2023": 74.5, "Mar 2024": 92.9, "TTM": 105.1})
            ]
        ),
        "balance_sheet": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2019": 281, "Mar 2020": 281, "Mar 2021": 281, "Mar 2022": 281, "Mar 2023": 281, "Mar 2024": 275}),
                FinancialRow(metric="Reserves", values={"Mar 2019": 62094, "Mar 2020": 66442, "Mar 2021": 75588, "Mar 2022": 82127, "Mar 2023": 88924, "Mar 2024": 91850}),
                FinancialRow(metric="Borrowings", values={"Mar 2019": 125555, "Mar 2020": 141007, "Mar 2021": 132605, "Mar 2022": 123447, "Mar 2023": 118596, "Mar 2024": 115200}),
                FinancialRow(metric="Other Liabilities", values={"Mar 2019": 110984, "Mar 2020": 105820, "Mar 2021": 117240, "Mar 2022": 132450, "Mar 2023": 148900, "Mar 2024": 162400}),
                FinancialRow(metric="Total Liabilities", values={"Mar 2019": 298914, "Mar 2020": 313550, "Mar 2021": 325714, "Mar 2022": 338305, "Mar 2023": 356701, "Mar 2024": 369725}),
                FinancialRow(metric="Fixed Assets", values={"Mar 2019": 35440, "Mar 2020": 38900, "Mar 2021": 39500, "Mar 2022": 42100, "Mar 2023": 45800, "Mar 2024": 48900}),
                FinancialRow(metric="CWIP", values={"Mar 2019": 4120, "Mar 2020": 3890, "Mar 2021": 3650, "Mar 2022": 4250, "Mar 2023": 5100, "Mar 2024": 6200}),
                FinancialRow(metric="Investments", values={"Mar 2019": 24500, "Mar 2020": 26800, "Mar 2021": 38500, "Mar 2022": 42100, "Mar 2023": 45600, "Mar 2024": 49800}),
                FinancialRow(metric="Other Assets", values={"Mar 2019": 234854, "Mar 2020": 243960, "Mar 2021": 244064, "Mar 2022": 249855, "Mar 2023": 260201, "Mar 2024": 264825}),
                FinancialRow(metric="Total Assets", values={"Mar 2019": 298914, "Mar 2020": 313550, "Mar 2021": 325714, "Mar 2022": 338305, "Mar 2023": 356701, "Mar 2024": 369725})
            ]
        ),
        "cash_flow": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2019": 11840, "Mar 2020": 13950, "Mar 2021": 22110, "Mar 2022": 18450, "Mar 2023": 21890, "Mar 2024": 25420}),
                FinancialRow(metric="Cash from Investing Activity", values={"Mar 2019": -8900, "Mar 2020": -7800, "Mar 2021": -5400, "Mar 2022": -6200, "Mar 2023": -7100, "Mar 2024": -8500}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2019": 6500, "Mar 2020": 5800, "Mar 2021": 4200, "Mar 2022": 5100, "Mar 2023": 6200, "Mar 2024": 7400}),
                FinancialRow(metric="Cash from Financing Activity", values={"Mar 2019": -2400, "Mar 2020": -5100, "Mar 2021": -14800, "Mar 2022": -11500, "Mar 2023": -13900, "Mar 2024": -16200}),
                FinancialRow(metric="Net Cash Flow", values={"Mar 2019": 540, "Mar 2020": 1050, "Mar 2021": 1910, "Mar 2022": 750, "Mar 2023": 890, "Mar 2024": 720})
            ]
        ),
        "concall_insights": [
            ConcallInsight(
                period="Q3 FY25 (Dec 2024)",
                transcript_url="https://www.screener.in/company/LT/consolidated/#documents",
                presentation_url="https://www.screener.in/company/LT/consolidated/#documents",
                cfo_and_fcf_analysis="Operational cash flow generation remained strong at Rs 6,800 Cr with working capital intensity dropping to 11.8% of sales (vs 12.2% in FY24). Free cash flow generation post-capex stood at Rs 4,950 Cr.",
                demand_drivers=[
                    "Consolidated Order Book reached all-time high of Rs 5,10,000 Cr (+19% YoY), providing 2.5+ years of revenue visibility.",
                    "International order inflow grew 45% YoY, dominated by mega hydrocarbon & renewable energy contracts in Saudi Arabia / Middle East.",
                    "Domestic infrastructure ordering saw healthy momentum in solar EPC, high-speed rail, and transmission lines."
                ],
                supply_and_capex=[
                    "Green hydrogen electrolyzer manufacturing facility in Hazira achieving commercial run-rate.",
                    "Semiconductor fab design center scaling hiring."
                ],
                management_guidance="Management upgraded full-year order inflow guidance to 15-18% YoY and guided for core EPC EBITDA margins expanding to 8.5-9.0% as legacy fixed-price orders get executed.",
                risks_and_headwinds=[
                    "Middle East geopolitical tensions or project execution delays.",
                    "Supply chain bottlenecks for specialized turbines and electrical equipment."
                ],
                analyst_sentiment="Bullish - Direct proxy to the massive India and Middle East capex super-cycle with unprecedented order book visibility."
            )
        ],
        "annual_report_insights": [
            AnnualReportInsight(
                year="FY 2024",
                report_url="https://www.screener.in/company/LT/consolidated/#documents",
                cfo_fcf_performance="CFO was Rs 25,420 Cr (195% of PAT). FCF was Rs 18,020 Cr.",
                capex_cwip_summary="Completed share buyback of Rs 10,000 Cr; continuing asset-light Lakshya 2026 roadmap.",
                strategic_priorities=[
                    "Divesting non-core concessions (Hyderabad Metro restructuring, Nabha Power).",
                    "Scaling Hi-Tech manufacturing in Defense, Electrolyzers, and Data Centers.",
                    "Expanding Middle East offshore hydrocarbon footprint."
                ],
                forensic_checklist={
                    "promoter_pledge": "0.0% (Professionally managed, zero promoter pledge)",
                    "auditor_qualification": "Unmodified / Clean Audit Report by Deloitte",
                    "related_party_transactions": "Arms-length subsidiary EPC contracts",
                    "contingent_liabilities": "Guarantees against performance contracts in normal EPC course"
                }
            )
        ],
        "documents": DocumentLinks(
            annual_reports=[
                {"name": "Annual Report FY24", "url": "https://www.screener.in/company/LT/consolidated/#documents"}
            ],
            concalls=[
                {"name": "Q3 FY25 Earnings Call Transcript", "url": "https://www.screener.in/company/LT/consolidated/#documents"}
            ],
            presentations=[
                {"name": "Q3 FY25 Investor Presentation", "url": "https://www.screener.in/company/LT/consolidated/#documents"}
            ]
        )
    },
    "TATAMOTORS": {
        "symbol": "TATAMOTORS",
        "name": "Tata Motors Ltd",
        "sector": "Automobile",
        "industry": "Commercial Vehicles / Passenger Vehicles / EV / JLR",
        "about": "Tata Motors Limited is a leading global automobile manufacturer with an extensive portfolio of cars, sports utility vehicles, trucks, buses and defense vehicles. It is India's market leader in electric passenger vehicles and commercial vehicles, and owns the iconic Jaguar Land Rover (JLR) brand.",
        "ratios": KeyRatios(
            market_cap_cr=345000.0,
            current_price=940.0,
            high_low="1179 / 680",
            stock_pe=10.8,
            book_value=245.0,
            dividend_yield_pct=0.64,
            roce_pct=21.4,
            roe_pct=34.2,
            face_value=2.0,
            industry_pe=22.5,
            debt_to_equity=0.45,
            interest_coverage=8.9,
            fcf_yield_pct=8.5,
            sales_growth_3yr_cagr=24.5,
            profit_growth_3yr_cagr=85.0
        ),
        "quarters": FinancialStatement(
            periods=["Dec 2022", "Mar 2023", "Jun 2023", "Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024"],
            rows=[
                FinancialRow(metric="Sales", values={"Dec 2022": 88489, "Mar 2023": 105932, "Jun 2023": 102236, "Sep 2023": 105128, "Dec 2023": 110577, "Mar 2024": 119986, "Jun 2024": 108048, "Sep 2024": 101450, "Dec 2024": 114000}),
                FinancialRow(metric="Expenses", values={"Dec 2022": 77800, "Mar 2023": 92100, "Jun 2023": 88700, "Sep 2023": 90500, "Dec 2023": 94800, "Mar 2024": 102500, "Jun 2024": 92600, "Sep 2024": 89800, "Dec 2024": 98200}),
                FinancialRow(metric="Operating Profit", values={"Dec 2022": 10689, "Mar 2023": 13832, "Jun 2023": 13536, "Sep 2023": 14628, "Dec 2023": 15777, "Mar 2024": 17486, "Jun 2024": 15448, "Sep 2024": 11650, "Dec 2024": 15800}),
                FinancialRow(metric="OPM %", values={"Dec 2022": 12.1, "Mar 2023": 13.1, "Jun 2023": 13.2, "Sep 2023": 13.9, "Dec 2023": 14.3, "Mar 2024": 14.6, "Jun 2024": 14.3, "Sep 2024": 11.5, "Dec 2024": 13.9}),
                FinancialRow(metric="Other Income", values={"Dec 2022": 820, "Mar 2023": 940, "Jun 2023": 1120, "Sep 2023": 1240, "Dec 2023": 1350, "Mar 2024": 1560, "Jun 2024": 1420, "Sep 2024": 1150, "Dec 2024": 1300}),
                FinancialRow(metric="Interest", values={"Dec 2022": 2676, "Mar 2023": 2540, "Jun 2023": 2610, "Sep 2023": 2650, "Dec 2023": 2480, "Mar 2024": 2350, "Jun 2024": 2180, "Sep 2024": 2100, "Dec 2024": 1950}),
                FinancialRow(metric="Depreciation", values={"Dec 2022": 5834, "Mar 2023": 6120, "Jun 2023": 6250, "Sep 2023": 6480, "Dec 2023": 6620, "Mar 2024": 6980, "Jun 2024": 6850, "Sep 2024": 6720, "Dec 2024": 6900}),
                FinancialRow(metric="Profit before tax", values={"Dec 2022": 3000, "Mar 2023": 6112, "Jun 2023": 5796, "Sep 2023": 6738, "Dec 2023": 8027, "Mar 2024": 9716, "Jun 2024": 7838, "Sep 2024": 3980, "Dec 2024": 8250}),
                FinancialRow(metric="Tax %", values={"Dec 2022": -1.0, "Mar 2023": 12.0, "Jun 2023": 44.0, "Sep 2023": 44.0, "Dec 2023": 12.0, "Mar 2024": -80.0, "Jun 2024": 30.0, "Sep 2024": 13.0, "Dec 2024": 22.0}),
                FinancialRow(metric="Net Profit", values={"Dec 2022": 3043, "Mar 2023": 5496, "Jun 2023": 3301, "Sep 2023": 3832, "Dec 2023": 7145, "Mar 2024": 17407, "Jun 2024": 5566, "Sep 2024": 3450, "Dec 2024": 6435}),
                FinancialRow(metric="EPS in Rs", values={"Dec 2022": 7.9, "Mar 2023": 14.3, "Jun 2023": 8.6, "Sep 2023": 10.0, "Dec 2023": 18.6, "Mar 2024": 45.4, "Jun 2024": 14.5, "Sep 2024": 9.0, "Dec 2024": 16.8})
            ]
        ),
        "profit_loss": FinancialStatement(
            periods=["Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "TTM"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2018": 291550, "Mar 2019": 301938, "Mar 2020": 261068, "Mar 2021": 249795, "Mar 2022": 278454, "Mar 2023": 345967, "Mar 2024": 437928, "TTM": 443534}),
                FinancialRow(metric="Expenses", values={"Mar 2018": 258816, "Mar 2019": 272118, "Mar 2020": 241347, "Mar 2021": 217983, "Mar 2022": 253634, "Mar 2023": 314151, "Mar 2024": 380840, "TTM": 383100}),
                FinancialRow(metric="Operating Profit", values={"Mar 2018": 32734, "Mar 2019": 29820, "Mar 2020": 19721, "Mar 2021": 31812, "Mar 2022": 24820, "Mar 2023": 31816, "Mar 2024": 57088, "TTM": 60434}),
                FinancialRow(metric="OPM %", values={"Mar 2018": 11.2, "Mar 2019": 9.9, "Mar 2020": 7.6, "Mar 2021": 12.7, "Mar 2022": 8.9, "Mar 2023": 9.2, "Mar 2024": 13.0, "TTM": 13.6}),
                FinancialRow(metric="Other Income", values={"Mar 2018": 2686, "Mar 2019": 2965, "Mar 2020": 2973, "Mar 2021": 2643, "Mar 2022": 2650, "Mar 2023": 3720, "Mar 2024": 5270, "TTM": 5170}),
                FinancialRow(metric="Interest", values={"Mar 2018": 4682, "Mar 2019": 5759, "Mar 2020": 7243, "Mar 2021": 8097, "Mar 2022": 9312, "Mar 2023": 10225, "Mar 2024": 10090, "TTM": 8580}),
                FinancialRow(metric="Depreciation", values={"Mar 2018": 21554, "Mar 2019": 23591, "Mar 2020": 21425, "Mar 2021": 23547, "Mar 2022": 24836, "Mar 2023": 24860, "Mar 2024": 26330, "TTM": 27320}),
                FinancialRow(metric="Profit before tax", values={"Mar 2018": 9184, "Mar 2019": 3435, "Mar 2020": -5974, "Mar 2021": 2811, "Mar 2022": -6678, "Mar 2023": 451, "Mar 2024": 30278, "TTM": 29714}),
                FinancialRow(metric="Tax %", values={"Mar 2018": 26.0, "Mar 2019": 50.0, "Mar 2020": -20.0, "Mar 2021": 150.0, "Mar 2022": -70.0, "Mar 2023": -470.0, "Mar 2024": -6.0, "TTM": 15.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2018": 6813, "Mar 2019": -29314, "Mar 2020": -11971, "Mar 2021": -13395, "Mar 2022": -11309, "Mar 2023": 2690, "Mar 2024": 31807, "TTM": 32851}),
                FinancialRow(metric="EPS in Rs", values={"Mar 2018": 19.9, "Mar 2019": -85.7, "Mar 2020": -35.0, "Mar 2021": -35.0, "Mar 2022": -29.6, "Mar 2023": 7.0, "Mar 2024": 82.9, "TTM": 85.6})
            ]
        ),
        "balance_sheet": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2019": 679, "Mar 2020": 720, "Mar 2021": 766, "Mar 2022": 766, "Mar 2023": 766, "Mar 2024": 766}),
                FinancialRow(metric="Reserves", values={"Mar 2019": 59500, "Mar 2020": 61490, "Mar 2021": 54480, "Mar 2022": 43795, "Mar 2023": 44556, "Mar 2024": 84150}),
                FinancialRow(metric="Borrowings", values={"Mar 2019": 106115, "Mar 2020": 118810, "Mar 2021": 142130, "Mar 2022": 146449, "Mar 2023": 134113, "Mar 2024": 107520}),
                FinancialRow(metric="Other Liabilities", values={"Mar 2019": 140994, "Mar 2020": 141113, "Mar 2021": 145780, "Mar 2022": 139150, "Mar 2023": 155800, "Mar 2024": 172400}),
                FinancialRow(metric="Total Liabilities", values={"Mar 2019": 307288, "Mar 2020": 322133, "Mar 2021": 343156, "Mar 2022": 330160, "Mar 2023": 335235, "Mar 2024": 364836}),
                FinancialRow(metric="Fixed Assets", values={"Mar 2019": 154800, "Mar 2020": 152100, "Mar 2021": 151200, "Mar 2022": 139400, "Mar 2023": 137800, "Mar 2024": 146500}),
                FinancialRow(metric="CWIP", values={"Mar 2019": 30500, "Mar 2020": 26800, "Mar 2021": 21900, "Mar 2022": 15800, "Mar 2023": 18200, "Mar 2024": 22400}),
                FinancialRow(metric="Investments", values={"Mar 2019": 15700, "Mar 2020": 16400, "Mar 2021": 24600, "Mar 2022": 29800, "Mar 2023": 38900, "Mar 2024": 52100}),
                FinancialRow(metric="Other Assets", values={"Mar 2019": 106288, "Mar 2020": 126833, "Mar 2021": 145456, "Mar 2022": 145160, "Mar 2023": 140335, "Mar 2024": 143836}),
                FinancialRow(metric="Total Assets", values={"Mar 2019": 307288, "Mar 2020": 322133, "Mar 2021": 343156, "Mar 2022": 330160, "Mar 2023": 335235, "Mar 2024": 364836})
            ]
        ),
        "cash_flow": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2019": 18890, "Mar 2020": 26630, "Mar 2021": 29010, "Mar 2022": 14280, "Mar 2023": 36450, "Mar 2024": 62450}),
                FinancialRow(metric="Cash from Investing Activity", values={"Mar 2019": -28900, "Mar 2020": -29500, "Mar 2021": -19800, "Mar 2022": -15600, "Mar 2023": -22400, "Mar 2024": -33100}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2019": 27000, "Mar 2020": 25000, "Mar 2021": 18500, "Mar 2022": 14800, "Mar 2023": 21000, "Mar 2024": 29500}),
                FinancialRow(metric="Cash from Financing Activity", values={"Mar 2019": 11200, "Mar 2020": 7400, "Mar 2021": -4800, "Mar 2022": 3400, "Mar 2023": -12500, "Mar 2024": -28900}),
                FinancialRow(metric="Net Cash Flow", values={"Mar 2019": 1190, "Mar 2020": 4530, "Mar 2021": 4410, "Mar 2022": 2080, "Mar 2023": 1550, "Mar 2024": 450})
            ]
        ),
        "concall_insights": [
            ConcallInsight(
                period="Q3 FY25 (Dec 2024)",
                transcript_url="https://www.screener.in/company/TATAMOTORS/consolidated/#documents",
                presentation_url="https://www.screener.in/company/TATAMOTORS/consolidated/#documents",
                cfo_and_fcf_analysis="JLR generated positive Free Cash Flow of £523M in Q3, bringing JLR net cash positive milestone ahead of schedule. Total group CFO was Rs 14,200 Cr against Capex of Rs 7,800 Cr, yielding Rs 6,400 Cr net FCF.",
                demand_drivers=[
                    "Jio-order book for Range Rover, Defender, and Range Rover Sport remains resilient with 148,000 pending orders.",
                    "Domestic EV market share held at 68% bolstered by the Curvv.ev and Punch.ev launches.",
                    "Commercial vehicle fleet utilization stabilized at 72%, though infra construction slowdown created temporary Q3 volume lull."
                ],
                supply_and_capex=[
                    "Demerger into two listed entities (Commercial Vehicles business vs Passenger Vehicles / JLR / EV) progressing towards Q1 FY26 completion.",
                    "Agratas battery cell giga-factory in Somerset UK and Gujarat breaking ground."
                ],
                management_guidance="Management reiterated target of zero net auto debt for the combined entity in FY25, and guided for 8.5%+ EBIT margin for JLR over FY26.",
                risks_and_headwinds=[
                    "Aluminum supply chain disruption recovery at European suppliers.",
                    "Tariff risks in US and European automotive trade."
                ],
                analyst_sentiment="Constructive / High Free Cash Flow - Deleveraging complete, value unlocking via demerger upcoming."
            )
        ],
        "annual_report_insights": [
            AnnualReportInsight(
                year="FY 2024",
                report_url="https://www.screener.in/company/TATAMOTORS/consolidated/#documents",
                cfo_fcf_performance="CFO crossed record Rs 62,450 Cr. Free Cash Flow reached Rs 32,950 Cr, enabling Rs 26,000 Cr debt reduction.",
                capex_cwip_summary="CWIP of Rs 22,400 Cr focused on EMA electric vehicle architecture for JLR and Sanand plant upgrades.",
                strategic_priorities=[
                    "Executing the demerger into Commercial Vehicles vs Passenger Vehicles.",
                    "Electrifying the JLR lineup with pure electric Range Rover launch.",
                    "Maintaining CV market dominance while protecting pricing power."
                ],
                forensic_checklist={
                    "promoter_pledge": "0.0% (Zero pledge)",
                    "auditor_qualification": "Unmodified / Clean Audit Report by B S R & Co.",
                    "related_party_transactions": "Standard Tata group component procurement",
                    "contingent_liabilities": "Tax disputes under appeal within standard auto OEM norms"
                }
            )
        ],
        "documents": DocumentLinks(
            annual_reports=[
                {"name": "Annual Report FY24", "url": "https://www.screener.in/company/TATAMOTORS/consolidated/#documents"}
            ],
            concalls=[
                {"name": "Q3 FY25 Earnings Call Transcript", "url": "https://www.screener.in/company/TATAMOTORS/consolidated/#documents"}
            ],
            presentations=[
                {"name": "Q3 FY25 Investor Presentation", "url": "https://www.screener.in/company/TATAMOTORS/consolidated/#documents"}
            ]
        )
    },
    "ITC": {
        "symbol": "ITC",
        "name": "ITC Ltd",
        "sector": "Consumer Goods / FMCG",
        "industry": "FMCG / Cigarettes / Hotels / Paperboards / Agri",
        "about": "ITC is one of India's foremost private sector companies and a diversified conglomerate with businesses spanning Fast Moving Consumer Goods, Hotels, Paperboards & Packaging, Agri Business and Information Technology.",
        "ratios": KeyRatios(
            market_cap_cr=605000.0,
            current_price=485.0,
            high_low="528 / 399",
            stock_pe=28.5,
            book_value=58.0,
            dividend_yield_pct=3.10,
            roce_pct=39.5,
            roe_pct=31.2,
            face_value=1.0,
            industry_pe=38.0,
            debt_to_equity=0.01,
            interest_coverage=85.0,
            fcf_yield_pct=3.5,
            sales_growth_3yr_cagr=13.2,
            profit_growth_3yr_cagr=14.8
        ),
        "quarters": FinancialStatement(
            periods=["Dec 2022", "Mar 2023", "Jun 2023", "Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024"],
            rows=[
                FinancialRow(metric="Sales", values={"Dec 2022": 17165, "Mar 2023": 17506, "Jun 2023": 16843, "Sep 2023": 17549, "Dec 2023": 17483, "Mar 2024": 17752, "Jun 2024": 18220, "Sep 2024": 19327, "Dec 2024": 19800}),
                FinancialRow(metric="Expenses", values={"Dec 2022": 11063, "Mar 2023": 11300, "Jun 2023": 10593, "Sep 2023": 11508, "Dec 2023": 11459, "Mar 2024": 11589, "Jun 2024": 11925, "Sep 2024": 12892, "Dec 2024": 13100}),
                FinancialRow(metric="Operating Profit", values={"Dec 2022": 6102, "Mar 2023": 6206, "Jun 2023": 6250, "Sep 2023": 6041, "Dec 2023": 6024, "Mar 2024": 6163, "Jun 2024": 6295, "Sep 2024": 6435, "Dec 2024": 6700}),
                FinancialRow(metric="OPM %", values={"Dec 2022": 35.5, "Mar 2023": 35.4, "Jun 2023": 37.1, "Sep 2023": 34.4, "Dec 2023": 34.5, "Mar 2024": 34.7, "Jun 2024": 34.5, "Sep 2024": 33.3, "Dec 2024": 33.8}),
                FinancialRow(metric="Other Income", values={"Dec 2022": 870, "Mar 2023": 740, "Jun 2023": 708, "Sep 2023": 668, "Dec 2023": 892, "Mar 2024": 920, "Jun 2024": 740, "Sep 2024": 780, "Dec 2024": 820}),
                FinancialRow(metric="Interest", values={"Dec 2022": 12, "Mar 2023": 14, "Jun 2023": 12, "Sep 2023": 11, "Dec 2023": 13, "Mar 2024": 15, "Jun 2024": 12, "Sep 2024": 14, "Dec 2024": 13}),
                FinancialRow(metric="Depreciation", values={"Dec 2022": 454, "Mar 2023": 472, "Jun 2023": 416, "Sep 2023": 420, "Dec 2023": 435, "Mar 2024": 460, "Jun 2024": 440, "Sep 2024": 455, "Dec 2024": 465}),
                FinancialRow(metric="Profit before tax", values={"Dec 2022": 6506, "Mar 2023": 6460, "Jun 2023": 6530, "Sep 2023": 6278, "Dec 2023": 6468, "Mar 2024": 6608, "Jun 2024": 6583, "Sep 2024": 6746, "Dec 2024": 7042}),
                FinancialRow(metric="Tax %", values={"Dec 2022": 24.0, "Mar 2023": 23.0, "Jun 2023": 24.0, "Sep 2023": 24.0, "Dec 2023": 24.0, "Mar 2024": 25.0, "Jun 2024": 24.0, "Sep 2024": 25.0, "Dec 2024": 24.0}),
                FinancialRow(metric="Net Profit", values={"Dec 2022": 5070, "Mar 2023": 5175, "Jun 2023": 5180, "Sep 2023": 4964, "Dec 2023": 5335, "Mar 2024": 5120, "Jun 2024": 5092, "Sep 2024": 5054, "Dec 2024": 5350}),
                FinancialRow(metric="EPS in Rs", values={"Dec 2022": 4.1, "Mar 2023": 4.2, "Jun 2023": 4.2, "Sep 2023": 4.0, "Dec 2023": 4.3, "Mar 2024": 4.1, "Jun 2024": 4.1, "Sep 2024": 4.0, "Dec 2024": 4.3})
            ]
        ),
        "profit_loss": FinancialStatement(
            periods=["Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "TTM"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2018": 43449, "Mar 2019": 48353, "Mar 2020": 48900, "Mar 2021": 48525, "Mar 2022": 60668, "Mar 2023": 70251, "Mar 2024": 70870, "TTM": 75119}),
                FinancialRow(metric="Expenses", values={"Mar 2018": 26053, "Mar 2019": 28863, "Mar 2020": 29800, "Mar 2021": 31500, "Mar 2022": 39300, "Mar 2023": 44800, "Mar 2024": 45800, "TTM": 49400}),
                FinancialRow(metric="Operating Profit", values={"Mar 2018": 17396, "Mar 2019": 19490, "Mar 2020": 19100, "Mar 2021": 17025, "Mar 2022": 21368, "Mar 2023": 25451, "Mar 2024": 25070, "TTM": 25719}),
                FinancialRow(metric="OPM %", values={"Mar 2018": 40.0, "Mar 2019": 40.3, "Mar 2020": 39.1, "Mar 2021": 35.1, "Mar 2022": 35.2, "Mar 2023": 36.2, "Mar 2024": 35.4, "TTM": 34.2}),
                FinancialRow(metric="Other Income", values={"Mar 2018": 2133, "Mar 2019": 2485, "Mar 2020": 3014, "Mar 2021": 3251, "Mar 2022": 2590, "Mar 2023": 2437, "Mar 2024": 3180, "TTM": 3260}),
                FinancialRow(metric="Interest", values={"Mar 2018": 87, "Mar 2019": 45, "Mar 2020": 55, "Mar 2021": 44, "Mar 2022": 42, "Mar 2023": 48, "Mar 2024": 52, "TTM": 51}),
                FinancialRow(metric="Depreciation", values={"Mar 2018": 1236, "Mar 2019": 1397, "Mar 2020": 1645, "Mar 2021": 1646, "Mar 2022": 1732, "Mar 2023": 1762, "Mar 2024": 1790, "TTM": 1800}),
                FinancialRow(metric="Profit before tax", values={"Mar 2018": 18206, "Mar 2019": 20533, "Mar 2020": 20414, "Mar 2021": 18586, "Mar 2022": 22184, "Mar 2023": 26078, "Mar 2024": 26408, "TTM": 27128}),
                FinancialRow(metric="Tax %", values={"Mar 2018": 36.0, "Mar 2019": 35.0, "Mar 2020": 24.0, "Mar 2021": 25.0, "Mar 2022": 25.0, "Mar 2023": 24.0, "Mar 2024": 24.0, "TTM": 24.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2018": 11652, "Mar 2019": 13350, "Mar 2020": 15584, "Mar 2021": 13389, "Mar 2022": 15503, "Mar 2023": 19476, "Mar 2024": 20422, "TTM": 20616}),
                FinancialRow(metric="EPS in Rs", values={"Mar 2018": 9.5, "Mar 2019": 10.9, "Mar 2020": 12.7, "Mar 2021": 10.9, "Mar 2022": 12.6, "Mar 2023": 15.7, "Mar 2024": 16.4, "TTM": 16.5})
            ]
        ),
        "balance_sheet": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2019": 1226, "Mar 2020": 1229, "Mar 2021": 1231, "Mar 2022": 1232, "Mar 2023": 1243, "Mar 2024": 1248}),
                FinancialRow(metric="Reserves", values={"Mar 2019": 58240, "Mar 2020": 64000, "Mar 2021": 59000, "Mar 2022": 61400, "Mar 2023": 67800, "Mar 2024": 72400}),
                FinancialRow(metric="Borrowings", values={"Mar 2019": 8, "Mar 2020": 6, "Mar 2021": 5, "Mar 2022": 4, "Mar 2023": 4, "Mar 2024": 5}),
                FinancialRow(metric="Other Liabilities", values={"Mar 2019": 11840, "Mar 2020": 12450, "Mar 2021": 13200, "Mar 2022": 14500, "Mar 2023": 15600, "Mar 2024": 16800}),
                FinancialRow(metric="Total Liabilities", values={"Mar 2019": 71314, "Mar 2020": 77685, "Mar 2021": 73436, "Mar 2022": 77136, "Mar 2023": 84647, "Mar 2024": 90453}),
                FinancialRow(metric="Fixed Assets", values={"Mar 2019": 17800, "Mar 2020": 19400, "Mar 2021": 20500, "Mar 2022": 21800, "Mar 2023": 23400, "Mar 2024": 25100}),
                FinancialRow(metric="CWIP", values={"Mar 2019": 3500, "Mar 2020": 2800, "Mar 2021": 2400, "Mar 2022": 2600, "Mar 2023": 3100, "Mar 2024": 3400}),
                FinancialRow(metric="Investments", values={"Mar 2019": 28500, "Mar 2020": 32400, "Mar 2021": 29800, "Mar 2022": 31500, "Mar 2023": 36200, "Mar 2024": 38900}),
                FinancialRow(metric="Other Assets", values={"Mar 2019": 21514, "Mar 2020": 23085, "Mar 2021": 20736, "Mar 2022": 21236, "Mar 2023": 21947, "Mar 2024": 23053}),
                FinancialRow(metric="Total Assets", values={"Mar 2019": 71314, "Mar 2020": 77685, "Mar 2021": 73436, "Mar 2022": 77136, "Mar 2023": 84647, "Mar 2024": 90453})
            ]
        ),
        "cash_flow": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2019": 13940, "Mar 2020": 14850, "Mar 2021": 12520, "Mar 2022": 15850, "Mar 2023": 17820, "Mar 2024": 21450}),
                FinancialRow(metric="Cash from Investing Activity", values={"Mar 2019": -5400, "Mar 2020": -4200, "Mar 2021": -3100, "Mar 2022": -3800, "Mar 2023": -4200, "Mar 2024": -4900}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2019": 2800, "Mar 2020": 2400, "Mar 2021": 2100, "Mar 2022": 2300, "Mar 2023": 2600, "Mar 2024": 2900}),
                FinancialRow(metric="Cash from Financing Activity", values={"Mar 2019": -8400, "Mar 2020": -10200, "Mar 2021": -9800, "Mar 2022": -11800, "Mar 2023": -13500, "Mar 2024": -16400}),
                FinancialRow(metric="Net Cash Flow", values={"Mar 2019": 140, "Mar 2020": 450, "Mar 2021": -380, "Mar 2022": 250, "Mar 2023": 120, "Mar 2024": 150})
            ]
        ),
        "concall_insights": [
            ConcallInsight(
                period="Q3 FY25 (Dec 2024)",
                transcript_url="https://www.screener.in/company/ITC/consolidated/#documents",
                presentation_url="https://www.screener.in/company/ITC/consolidated/#documents",
                cfo_and_fcf_analysis="Cash conversion remains pristine at >105% of net profit. Cash & liquid investments crossed Rs 42,000 Cr with zero net debt. FCF generation for Q3 reached Rs 4,800 Cr.",
                demand_drivers=[
                    "Cigarette volume growth held steady at 3-4% YoY with stable taxation and market share gains from illicit trade.",
                    "FMCG-Others grew 7.8% YoY led by Foods (Aashirvaad, Sunfeast, Bingo!) and Personal Care (Savlon, Fiama).",
                    "Agri Business revenue surged 22% YoY on value-added exports of coffee, leaf tobacco, and spices."
                ],
                supply_and_capex=[
                    "Hotels business demerger into ITC Hotels Ltd completed, unlocking capital efficiency and improving group ROCE.",
                    "Integrated Consumer Goods Manufacturing and Logistics (ICML) facilities expansion progressing on budget."
                ],
                management_guidance="Management committed to 80-85% dividend payout ratio, sustained FMCG-Others EBITDA margin expansion of 100-120 bps annually, and high cash returns.",
                risks_and_headwinds=[
                    "Raw material inflation in wheat, cocoa, and edible oils impacting FMCG gross margins.",
                    "Paperboards division facing low-priced imports from China and high wood costs."
                ],
                analyst_sentiment="Bullish / High Dividend Safety - Rock-solid balance sheet, FMCG margin expansion, and high dividend yield."
            )
        ],
        "annual_report_insights": [
            AnnualReportInsight(
                year="FY 2024",
                report_url="https://www.screener.in/company/ITC/consolidated/#documents",
                cfo_fcf_performance="CFO reached Rs 21,450 Cr (105% of PAT). FCF was Rs 18,550 Cr, yielding a 3.5% FCF yield.",
                capex_cwip_summary="Capex of Rs 2,900 Cr directed toward ICML plants and sustainable packaging facilities.",
                strategic_priorities=[
                    "Scaling 'ITC Next' digital and direct-to-consumer FMCG brands.",
                    "Asset-right strategy for Hotels under newly demerged entity.",
                    "Expanding climate-smart agriculture and value-added agri exports."
                ],
                forensic_checklist={
                    "promoter_pledge": "0.0% (No promoter, institutional/retail held)",
                    "auditor_qualification": "Unmodified / Clean Audit Report by S R B C & CO",
                    "related_party_transactions": "Standard operating business transactions",
                    "contingent_liabilities": "Excise and tax matters pending adjudication in appellate tribunals"
                }
            )
        ],
        "documents": DocumentLinks(
            annual_reports=[
                {"name": "Annual Report FY24", "url": "https://www.screener.in/company/ITC/consolidated/#documents"}
            ],
            concalls=[
                {"name": "Q3 FY25 Earnings Call Transcript", "url": "https://www.screener.in/company/ITC/consolidated/#documents"}
            ],
            presentations=[
                {"name": "Q3 FY25 Investor Presentation", "url": "https://www.screener.in/company/ITC/consolidated/#documents"}
            ]
        )
    },
    "HDFCBANK": {
        "symbol": "HDFCBANK",
        "name": "HDFC Bank Ltd",
        "sector": "Banking & Financial Services",
        "industry": "Private Sector Bank",
        "about": "HDFC Bank is India's leading private sector bank and one of the largest financial conglomerates in the world post its merger with HDFC Limited. It has a nationwide distribution network of over 8,800 branches serving over 90 million customers.",
        "ratios": KeyRatios(
            market_cap_cr=1380000.0,
            current_price=1810.0,
            high_low="1885 / 1363",
            stock_pe=19.4,
            book_value=610.0,
            dividend_yield_pct=1.08,
            roce_pct=17.2,
            roe_pct=16.5,
            face_value=1.0,
            industry_pe=18.5,
            debt_to_equity=6.8,
            interest_coverage=2.4,
            fcf_yield_pct=3.8,
            sales_growth_3yr_cagr=28.5,
            profit_growth_3yr_cagr=21.2
        ),
        "quarters": FinancialStatement(
            periods=["Dec 2022", "Mar 2023", "Jun 2023", "Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024"],
            rows=[
                FinancialRow(metric="Sales", values={"Dec 2022": 45145, "Mar 2023": 47715, "Jun 2023": 51168, "Sep 2023": 66317, "Dec 2023": 70582, "Mar 2024": 71700, "Jun 2024": 73200, "Sep 2024": 74500, "Dec 2024": 77200}),
                FinancialRow(metric="Expenses", values={"Dec 2022": 26117, "Mar 2023": 28620, "Jun 2023": 30040, "Sep 2023": 43620, "Dec 2023": 47250, "Mar 2024": 47800, "Jun 2024": 48900, "Sep 2024": 49800, "Dec 2024": 51200}),
                FinancialRow(metric="Operating Profit", values={"Dec 2022": 19028, "Mar 2023": 19095, "Jun 2023": 21128, "Sep 2023": 22697, "Dec 2023": 23332, "Mar 2024": 23900, "Jun 2024": 24300, "Sep 2024": 24700, "Dec 2024": 26000}),
                FinancialRow(metric="OPM %", values={"Dec 2022": 42.1, "Mar 2023": 40.0, "Jun 2023": 41.3, "Sep 2023": 34.2, "Dec 2023": 33.1, "Mar 2024": 33.3, "Jun 2024": 33.2, "Sep 2024": 33.2, "Dec 2024": 33.7}),
                FinancialRow(metric="Other Income", values={"Dec 2022": 6120, "Mar 2023": 7100, "Jun 2023": 8200, "Sep 2023": 9500, "Dec 2023": 10200, "Mar 2024": 11100, "Jun 2024": 10800, "Sep 2024": 11400, "Dec 2024": 12100}),
                FinancialRow(metric="Interest", values={"Dec 2022": 17200, "Mar 2023": 19100, "Jun 2023": 20400, "Sep 2023": 33800, "Dec 2023": 37200, "Mar 2024": 38100, "Jun 2024": 39200, "Sep 2024": 39900, "Dec 2024": 40800}),
                FinancialRow(metric="Depreciation", values={"Dec 2022": 720, "Mar 2023": 780, "Jun 2023": 810, "Sep 2023": 920, "Dec 2023": 980, "Mar 2024": 1050, "Jun 2024": 1080, "Sep 2024": 1110, "Dec 2024": 1150}),
                FinancialRow(metric="Profit before tax", values={"Dec 2022": 16400, "Mar 2023": 16100, "Jun 2023": 16200, "Sep 2023": 21800, "Dec 2023": 22100, "Mar 2024": 22800, "Jun 2024": 22200, "Sep 2024": 23400, "Dec 2024": 24900}),
                FinancialRow(metric="Tax %", values={"Dec 2022": 23.0, "Mar 2023": 23.0, "Jun 2023": 24.0, "Sep 2023": 22.0, "Dec 2023": 24.0, "Mar 2024": 23.0, "Jun 2024": 24.0, "Sep 2024": 24.0, "Dec 2024": 24.0}),
                FinancialRow(metric="Net Profit", values={"Dec 2022": 12698, "Mar 2023": 12594, "Jun 2023": 12370, "Sep 2023": 16811, "Dec 2023": 16821, "Mar 2024": 17622, "Jun 2024": 16474, "Sep 2024": 17825, "Dec 2024": 18920}),
                FinancialRow(metric="EPS in Rs", values={"Dec 2022": 22.8, "Mar 2023": 22.5, "Jun 2023": 22.1, "Sep 2023": 22.2, "Dec 2023": 22.1, "Mar 2024": 23.2, "Jun 2024": 21.6, "Sep 2024": 23.4, "Dec 2024": 24.8})
            ]
        ),
        "profit_loss": FinancialStatement(
            periods=["Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "TTM"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2018": 80241, "Mar 2019": 98972, "Mar 2020": 114812, "Mar 2021": 120857, "Mar 2022": 127678, "Mar 2023": 161585, "Mar 2024": 258043, "TTM": 296600}),
                FinancialRow(metric="Expenses", values={"Mar 2018": 47616, "Mar 2019": 59223, "Mar 2020": 66100, "Mar 2021": 63400, "Mar 2022": 63600, "Mar 2023": 89400, "Mar 2024": 167500, "TTM": 197800}),
                FinancialRow(metric="Operating Profit", values={"Mar 2018": 32625, "Mar 2019": 39749, "Mar 2020": 48712, "Mar 2021": 57457, "Mar 2022": 64078, "Mar 2023": 72185, "Mar 2024": 90543, "TTM": 98800}),
                FinancialRow(metric="OPM %", values={"Mar 2018": 40.7, "Mar 2019": 40.2, "Mar 2020": 42.4, "Mar 2021": 47.5, "Mar 2022": 50.2, "Mar 2023": 44.7, "Mar 2024": 35.1, "TTM": 33.3}),
                FinancialRow(metric="Other Income", values={"Mar 2018": 15220, "Mar 2019": 17626, "Mar 2020": 23260, "Mar 2021": 25200, "Mar 2022": 29500, "Mar 2023": 31200, "Mar 2024": 42100, "TTM": 45700}),
                FinancialRow(metric="Interest", values={"Mar 2018": 40145, "Mar 2019": 50742, "Mar 2020": 58800, "Mar 2021": 55900, "Mar 2022": 55600, "Mar 2023": 74700, "Mar 2024": 139800, "TTM": 158000}),
                FinancialRow(metric="Depreciation", values={"Mar 2018": 2100, "Mar 2019": 2400, "Mar 2020": 2900, "Mar 2021": 3100, "Mar 2022": 3300, "Mar 2023": 3600, "Mar 2024": 4100, "TTM": 4490}),
                FinancialRow(metric="Profit before tax", values={"Mar 2018": 26860, "Mar 2019": 32180, "Mar 2020": 37250, "Mar 2021": 42480, "Mar 2022": 49800, "Mar 2023": 58300, "Mar 2024": 83600, "TTM": 93200}),
                FinancialRow(metric="Tax %", values={"Mar 2018": 34.0, "Mar 2019": 34.0, "Mar 2020": 29.0, "Mar 2021": 25.0, "Mar 2022": 26.0, "Mar 2023": 24.0, "Mar 2024": 23.0, "TTM": 24.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2018": 18510, "Mar 2019": 22446, "Mar 2020": 27254, "Mar 2021": 31833, "Mar 2022": 38053, "Mar 2023": 45997, "Mar 2024": 64062, "TTM": 70841}),
                FinancialRow(metric="EPS in Rs", values={"Mar 2018": 35.8, "Mar 2019": 41.3, "Mar 2020": 49.7, "Mar 2021": 57.8, "Mar 2022": 68.7, "Mar 2023": 82.3, "Mar 2024": 84.3, "TTM": 93.0})
            ]
        ),
        "balance_sheet": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2019": 544, "Mar 2020": 548, "Mar 2021": 551, "Mar 2022": 554, "Mar 2023": 558, "Mar 2024": 760}),
                FinancialRow(metric="Reserves", values={"Mar 2019": 148660, "Mar 2020": 170438, "Mar 2021": 203170, "Mar 2022": 239538, "Mar 2023": 280199, "Mar 2024": 461240}),
                FinancialRow(metric="Borrowings", values={"Mar 2019": 117085, "Mar 2020": 144628, "Mar 2021": 135487, "Mar 2022": 184817, "Mar 2023": 206766, "Mar 2024": 668900}),
                FinancialRow(metric="Other Liabilities", values={"Mar 2019": 978450, "Mar 2020": 1198540, "Mar 2021": 1386540, "Mar 2022": 1640500, "Mar 2023": 1948500, "Mar 2024": 2528000}),
                FinancialRow(metric="Total Liabilities", values={"Mar 2019": 1244739, "Mar 2020": 1514154, "Mar 2021": 1725748, "Mar 2022": 2065409, "Mar 2023": 2436029, "Mar 2024": 3658900}),
                FinancialRow(metric="Fixed Assets", values={"Mar 2019": 4030, "Mar 2020": 4431, "Mar 2021": 4909, "Mar 2022": 6084, "Mar 2023": 8046, "Mar 2024": 12100}),
                FinancialRow(metric="CWIP", values={"Mar 2019": 450, "Mar 2020": 510, "Mar 2021": 560, "Mar 2022": 620, "Mar 2023": 780, "Mar 2024": 950}),
                FinancialRow(metric="Investments", values={"Mar 2019": 290588, "Mar 2020": 391827, "Mar 2021": 443728, "Mar 2022": 455536, "Mar 2023": 517001, "Mar 2024": 703500}),
                FinancialRow(metric="Other Assets", values={"Mar 2019": 949671, "Mar 2020": 1117386, "Mar 2021": 1276551, "Mar 2022": 1603709, "Mar 2023": 1910202, "Mar 2024": 2942350}),
                FinancialRow(metric="Total Assets", values={"Mar 2019": 1244739, "Mar 2020": 1514154, "Mar 2021": 1725748, "Mar 2022": 2065409, "Mar 2023": 2436029, "Mar 2024": 3658900})
            ]
        ),
        "cash_flow": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2019": 31400, "Mar 2020": 38900, "Mar 2021": 42500, "Mar 2022": 46800, "Mar 2023": 54200, "Mar 2024": 78500}),
                FinancialRow(metric="Cash from Investing Activity", values={"Mar 2019": -14200, "Mar 2020": -18500, "Mar 2021": -21000, "Mar 2022": -24500, "Mar 2023": -29000, "Mar 2024": -42000}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2019": 1800, "Mar 2020": 2100, "Mar 2021": 2400, "Mar 2022": 2800, "Mar 2023": 3400, "Mar 2024": 4200}),
                FinancialRow(metric="Cash from Financing Activity", values={"Mar 2019": -12000, "Mar 2020": -15000, "Mar 2021": -18000, "Mar 2022": -19500, "Mar 2023": -22000, "Mar 2024": -32000}),
                FinancialRow(metric="Net Cash Flow", values={"Mar 2019": 5200, "Mar 2020": 5400, "Mar 2021": 3500, "Mar 2022": 2800, "Mar 2023": 3200, "Mar 2024": 4500})
            ]
        ),
        "concall_insights": [
            ConcallInsight(
                period="Q3 FY25 (Dec 2024)",
                transcript_url="https://www.screener.in/company/HDFCBANK/consolidated/#documents",
                presentation_url="https://www.screener.in/company/HDFCBANK/consolidated/#documents",
                cfo_and_fcf_analysis="Deposit mobilization accelerated to 16.5% YoY, outpacing loan growth (11.2% YoY) to successfully lower the Credit-to-Deposit (CD) ratio towards 98%. Net Interest Income grew 10.4% YoY.",
                demand_drivers=[
                    "Retail mortgage disbursement via merged HDFC branches crossed Rs 24,000 Cr in the quarter.",
                    "Gross NPA maintained pristine quality at 1.36% and Net NPA at 0.41%.",
                    "CASA ratio improved to 37.2% supported by retail branch density."
                ],
                supply_and_capex=[
                    "Branch expansion moderated to ~300 branches/year to maximize operational productivity per branch.",
                    "Digital 'PayZapp' and enterprise trade portals processing over 55M transactions monthly."
                ],
                management_guidance="Management reiterated target of returning Return on Assets (RoA) to 1.9-2.0% within 4-6 quarters as higher-cost HDFC borrowings get replaced with low-cost retail deposits.",
                risks_and_headwinds=[
                    "Industry-wide deposit rate competition keeping Cost of Funds elevated.",
                    "Slower corporate credit spread expansion."
                ],
                analyst_sentiment="Constructive / Value Buy - Merger overhang recedes as CD ratio normalizes, offering rare margin of safety for India's banking bellwether."
            )
        ],
        "annual_report_insights": [
            AnnualReportInsight(
                year="FY 2024",
                report_url="https://www.screener.in/company/HDFCBANK/consolidated/#documents",
                cfo_fcf_performance="Operating profit grew to Rs 90,543 Cr. Net Profit crossed Rs 64,062 Cr post-merger.",
                capex_cwip_summary="Tech and branch infrastructure investments stood at Rs 4,200 Cr.",
                strategic_priorities=[
                    "Cross-selling banking products to 10M+ exclusive mortgage customers.",
                    "Unlocking value in HDFC AMC, HDFC Life, and HDB Financial Services IPO.",
                    "Accelerating digital payments and commercial vehicle lending."
                ],
                forensic_checklist={
                    "promoter_pledge": "0.0% (No promoter, institutional/FII held)",
                    "auditor_qualification": "Unmodified / Clean Audit Report by Price Waterhouse & Co",
                    "related_party_transactions": "Standard group banking arrangements",
                    "contingent_liabilities": "Standard banking LC/BG letters of credit"
                }
            )
        ],
        "documents": DocumentLinks(
            annual_reports=[
                {"name": "Annual Report FY24", "url": "https://www.screener.in/company/HDFCBANK/consolidated/#documents"}
            ],
            concalls=[
                {"name": "Q3 FY25 Earnings Call Transcript", "url": "https://www.screener.in/company/HDFCBANK/consolidated/#documents"}
            ],
            presentations=[
                {"name": "Q3 FY25 Investor Presentation", "url": "https://www.screener.in/company/HDFCBANK/consolidated/#documents"}
            ]
        )
    },
    "INFY": {
        "symbol": "INFY",
        "name": "Infosys Ltd",
        "sector": "Information Technology",
        "industry": "IT Services & Software Consulting",
        "about": "Infosys is a global leader in next-generation digital services and consulting. It enables clients in more than 56 countries to navigate their digital transformation powered by Cloud and AI (Infosys Topaz).",
        "ratios": KeyRatios(
            market_cap_cr=780000.0,
            current_price=1870.0,
            high_low="1990 / 1358",
            stock_pe=28.8,
            book_value=210.0,
            dividend_yield_pct=2.15,
            roce_pct=40.5,
            roe_pct=31.8,
            face_value=5.0,
            industry_pe=30.1,
            debt_to_equity=0.08,
            interest_coverage=45.0,
            fcf_yield_pct=3.6,
            sales_growth_3yr_cagr=13.5,
            profit_growth_3yr_cagr=9.8
        ),
        "quarters": FinancialStatement(
            periods=["Dec 2022", "Mar 2023", "Jun 2023", "Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024"],
            rows=[
                FinancialRow(metric="Sales", values={"Dec 2022": 38318, "Mar 2023": 37441, "Jun 2023": 37933, "Sep 2023": 38994, "Dec 2023": 38821, "Mar 2024": 37923, "Jun 2024": 39315, "Sep 2024": 40986, "Dec 2024": 41800}),
                FinancialRow(metric="Expenses", values={"Dec 2022": 29424, "Mar 2023": 28833, "Jun 2023": 29696, "Sep 2023": 30510, "Dec 2023": 30440, "Mar 2024": 29900, "Jun 2024": 30810, "Sep 2024": 32180, "Dec 2024": 32700}),
                FinancialRow(metric="Operating Profit", values={"Dec 2022": 8894, "Mar 2023": 8608, "Jun 2023": 8237, "Sep 2023": 8484, "Dec 2023": 8381, "Mar 2024": 8023, "Jun 2024": 8505, "Sep 2024": 8806, "Dec 2024": 9100}),
                FinancialRow(metric="OPM %", values={"Dec 2022": 23.2, "Mar 2023": 23.0, "Jun 2023": 21.7, "Sep 2023": 21.8, "Dec 2023": 21.6, "Mar 2024": 21.2, "Jun 2024": 21.6, "Sep 2024": 21.5, "Dec 2024": 21.8}),
                FinancialRow(metric="Other Income", values={"Dec 2022": 692, "Mar 2023": 612, "Jun 2023": 472, "Sep 2023": 544, "Dec 2023": 732, "Mar 2024": 950, "Jun 2024": 820, "Sep 2024": 890, "Dec 2024": 940}),
                FinancialRow(metric="Interest", values={"Dec 2022": 72, "Mar 2023": 88, "Jun 2023": 102, "Sep 2023": 110, "Dec 2023": 105, "Mar 2024": 98, "Jun 2024": 110, "Sep 2024": 115, "Dec 2024": 110}),
                FinancialRow(metric="Depreciation", values={"Dec 2022": 1063, "Mar 2023": 1098, "Jun 2023": 1120, "Sep 2023": 1145, "Dec 2023": 1160, "Mar 2024": 1180, "Jun 2024": 1190, "Sep 2024": 1210, "Dec 2024": 1230}),
                FinancialRow(metric="Profit before tax", values={"Dec 2022": 8451, "Mar 2023": 8034, "Jun 2023": 7487, "Sep 2023": 7773, "Dec 2023": 7848, "Mar 2024": 7695, "Jun 2024": 8025, "Sep 2024": 8371, "Dec 2024": 8700}),
                FinancialRow(metric="Tax %", values={"Dec 2022": 22.0, "Mar 2023": 24.0, "Jun 2023": 21.0, "Sep 2023": 19.0, "Dec 2023": 22.0, "Mar 2024": -4.0, "Jun 2024": 21.0, "Sep 2024": 22.0, "Dec 2024": 23.0}),
                FinancialRow(metric="Net Profit", values={"Dec 2022": 6586, "Mar 2023": 6128, "Jun 2023": 5945, "Sep 2023": 6212, "Dec 2023": 6106, "Mar 2024": 7969, "Jun 2024": 6368, "Sep 2024": 6506, "Dec 2024": 6700}),
                FinancialRow(metric="EPS in Rs", values={"Dec 2022": 15.7, "Mar 2023": 14.7, "Jun 2023": 14.3, "Sep 2023": 15.0, "Dec 2023": 14.7, "Mar 2024": 19.2, "Jun 2024": 15.4, "Sep 2024": 15.7, "Dec 2024": 16.2})
            ]
        ),
        "profit_loss": FinancialStatement(
            periods=["Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "TTM"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2018": 70522, "Mar 2019": 82675, "Mar 2020": 90791, "Mar 2021": 100472, "Mar 2022": 121641, "Mar 2023": 146767, "Mar 2024": 153670, "TTM": 160024}),
                FinancialRow(metric="Expenses", values={"Mar 2018": 51522, "Mar 2019": 61875, "Mar 2020": 68500, "Mar 2021": 72580, "Mar 2022": 90200, "Mar 2023": 111600, "Mar 2024": 119500, "TTM": 125600}),
                FinancialRow(metric="Operating Profit", values={"Mar 2018": 19000, "Mar 2019": 20800, "Mar 2020": 22291, "Mar 2021": 27892, "Mar 2022": 31441, "Mar 2023": 35167, "Mar 2024": 34170, "TTM": 34424}),
                FinancialRow(metric="OPM %", values={"Mar 2018": 26.9, "Mar 2019": 25.2, "Mar 2020": 24.6, "Mar 2021": 27.8, "Mar 2022": 25.8, "Mar 2023": 24.0, "Mar 2024": 22.2, "TTM": 21.5}),
                FinancialRow(metric="Other Income", values={"Mar 2018": 3193, "Mar 2019": 2882, "Mar 2020": 2803, "Mar 2021": 2201, "Mar 2022": 2295, "Mar 2023": 2701, "Mar 2024": 3150, "TTM": 3600}),
                FinancialRow(metric="Interest", values={"Mar 2018": 0, "Mar 2019": 0, "Mar 2020": 170, "Mar 2021": 195, "Mar 2022": 200, "Mar 2023": 284, "Mar 2024": 415, "TTM": 433}),
                FinancialRow(metric="Depreciation", values={"Mar 2018": 1863, "Mar 2019": 2011, "Mar 2020": 2893, "Mar 2021": 3267, "Mar 2022": 3477, "Mar 2023": 4225, "Mar 2024": 4600, "TTM": 4810}),
                FinancialRow(metric="Profit before tax", values={"Mar 2018": 20330, "Mar 2019": 21671, "Mar 2020": 22031, "Mar 2021": 26631, "Mar 2022": 30059, "Mar 2023": 33359, "Mar 2024": 32305, "TTM": 32781}),
                FinancialRow(metric="Tax %", values={"Mar 2018": 21.0, "Mar 2019": 29.0, "Mar 2020": 25.0, "Mar 2021": 27.0, "Mar 2022": 27.0, "Mar 2023": 28.0, "Mar 2024": 19.0, "TTM": 21.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2018": 16029, "Mar 2019": 15404, "Mar 2020": 16594, "Mar 2021": 19351, "Mar 2022": 22110, "Mar 2023": 24095, "Mar 2024": 26233, "TTM": 27542}),
                FinancialRow(metric="EPS in Rs", values={"Mar 2018": 36.8, "Mar 2019": 35.4, "Mar 2020": 39.0, "Mar 2021": 45.6, "Mar 2022": 52.5, "Mar 2023": 57.6, "Mar 2024": 63.3, "TTM": 66.5})
            ]
        ),
        "balance_sheet": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2019": 2170, "Mar 2020": 2128, "Mar 2021": 2124, "Mar 2022": 2098, "Mar 2023": 2069, "Mar 2024": 2076}),
                FinancialRow(metric="Reserves", values={"Mar 2019": 62836, "Mar 2020": 63715, "Mar 2021": 74227, "Mar 2022": 73252, "Mar 2023": 73340, "Mar 2024": 83950}),
                FinancialRow(metric="Borrowings", values={"Mar 2019": 0, "Mar 2020": 4833, "Mar 2021": 5013, "Mar 2022": 5410, "Mar 2023": 8100, "Mar 2024": 8450}),
                FinancialRow(metric="Other Liabilities", values={"Mar 2019": 14948, "Mar 2020": 19688, "Mar 2021": 24200, "Mar 2022": 27500, "Mar 2023": 31200, "Mar 2024": 34800}),
                FinancialRow(metric="Total Liabilities", values={"Mar 2019": 79954, "Mar 2020": 90364, "Mar 2021": 105564, "Mar 2022": 108260, "Mar 2023": 114709, "Mar 2024": 129276}),
                FinancialRow(metric="Fixed Assets", values={"Mar 2019": 14100, "Mar 2020": 18200, "Mar 2021": 19100, "Mar 2022": 19800, "Mar 2023": 21200, "Mar 2024": 22400}),
                FinancialRow(metric="CWIP", values={"Mar 2019": 1150, "Mar 2020": 1020, "Mar 2021": 890, "Mar 2022": 950, "Mar 2023": 1120, "Mar 2024": 1280}),
                FinancialRow(metric="Investments", values={"Mar 2019": 22400, "Mar 2020": 24600, "Mar 2021": 29800, "Mar 2022": 28500, "Mar 2023": 29100, "Mar 2024": 34500}),
                FinancialRow(metric="Other Assets", values={"Mar 2019": 42304, "Mar 2020": 46544, "Mar 2021": 55774, "Mar 2022": 59010, "Mar 2023": 63289, "Mar 2024": 71096}),
                FinancialRow(metric="Total Assets", values={"Mar 2019": 79954, "Mar 2020": 90364, "Mar 2021": 105564, "Mar 2022": 108260, "Mar 2023": 114709, "Mar 2024": 129276})
            ]
        ),
        "cash_flow": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2019": 15850, "Mar 2020": 18560, "Mar 2021": 24100, "Mar 2022": 24960, "Mar 2023": 23400, "Mar 2024": 28900}),
                FinancialRow(metric="Cash from Investing Activity", values={"Mar 2019": -2100, "Mar 2020": -4500, "Mar 2021": -5800, "Mar 2022": -4200, "Mar 2023": -3800, "Mar 2024": -4600}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2019": 2400, "Mar 2020": 2600, "Mar 2021": 2200, "Mar 2022": 2500, "Mar 2023": 2700, "Mar 2024": 2800}),
                FinancialRow(metric="Cash from Financing Activity", values={"Mar 2019": -13900, "Mar 2020": -13800, "Mar 2021": -16500, "Mar 2022": -20800, "Mar 2023": -20100, "Mar 2024": -23400}),
                FinancialRow(metric="Net Cash Flow", values={"Mar 2019": -150, "Mar 2020": 260, "Mar 2021": 1800, "Mar 2022": -40, "Mar 2023": -500, "Mar 2024": 900})
            ]
        ),
        "concall_insights": [
            ConcallInsight(
                period="Q3 FY25 (Dec 2024)",
                transcript_url="https://www.screener.in/company/INFY/consolidated/#documents",
                presentation_url="https://www.screener.in/company/INFY/consolidated/#documents",
                cfo_and_fcf_analysis="Free Cash Flow conversion remained exceptional at 112% of Net Profit for Q3. Total CFO was Rs 7,850 Cr against capex of Rs 680 Cr, generating Rs 7,170 Cr of quarterly FCF.",
                demand_drivers=[
                    "Large deal TCV stood strong at $2.4B with 52% net new deal share.",
                    "Infosys Topaz (Generative AI platform) being integrated into over 200 client engagements.",
                    "Financial services and manufacturing verticals returned to sequential growth (+2.4% and +1.8% QoQ)."
                ],
                supply_and_capex=[
                    "Employee attrition stabilized at 12.9% LTM.",
                    "Operating margin expanded to 21.8% backed by 'Project Maximus' cost-optimization program."
                ],
                management_guidance="Management raised full-year FY25 constant-currency revenue growth guidance to 4.5%-5.0% (from 3.75%-4.5%) and maintained operating margin band at 20-22%.",
                risks_and_headwinds=[
                    "Decision-making cycles for non-essential discretionary tech consulting remain prolonged.",
                    "H1-B visa / regulatory shifts in US enterprise client spending."
                ],
                analyst_sentiment="Constructive - Reliable dividend compounding with expanding free cash flow."
            )
        ],
        "annual_report_insights": [
            AnnualReportInsight(
                year="FY 2024",
                report_url="https://www.screener.in/company/INFY/consolidated/#documents",
                cfo_fcf_performance="CFO was Rs 28,900 Cr (110% of PAT). FCF was Rs 26,100 Cr, returning 85% to shareholders via dividends.",
                capex_cwip_summary="Capex of Rs 2,800 Cr focused on AI cloud infrastructure and modern campus delivery hubs.",
                strategic_priorities=[
                    "Scaling Infosys Cobalt (Cloud) and Infosys Topaz (AI).",
                    "Strengthening presence in Nordic and Japanese regional markets.",
                    "Deepening domain capabilities via targeted tuck-in acquisitions (InSemi, in-tech)."
                ],
                forensic_checklist={
                    "promoter_pledge": "0.0% (Zero pledge)",
                    "auditor_qualification": "Unmodified / Clean Audit Report by Deloitte",
                    "related_party_transactions": "Standard arms-length board approved disclosures",
                    "contingent_liabilities": "Income tax demand matters pending before courts"
                }
            )
        ],
        "documents": DocumentLinks(
            annual_reports=[
                {"name": "Annual Report FY24", "url": "https://www.screener.in/company/INFY/consolidated/#documents"}
            ],
            concalls=[
                {"name": "Q3 FY25 Earnings Call Transcript", "url": "https://www.screener.in/company/INFY/consolidated/#documents"}
            ],
            presentations=[
                {"name": "Q3 FY25 Investor Presentation", "url": "https://www.screener.in/company/INFY/consolidated/#documents"}
            ]
        )
    },
    "ICICIBANK": {
        "symbol": "ICICIBANK",
        "name": "ICICI Bank Ltd",
        "sector": "Banking & Financial Services",
        "industry": "Private Sector Bank",
        "about": "ICICI Bank is a leading private sector bank in India. The Bank offers a wide range of banking products and financial services to corporate and retail customers through a variety of delivery channels and through its group companies.",
        "ratios": KeyRatios(
            market_cap_cr=910000.0,
            current_price=1290.0,
            high_low="1362 / 985",
            stock_pe=19.2,
            book_value=385.0,
            dividend_yield_pct=0.78,
            roce_pct=18.4,
            roe_pct=18.9,
            face_value=2.0,
            industry_pe=18.5,
            debt_to_equity=6.2,
            interest_coverage=2.8,
            fcf_yield_pct=3.9,
            sales_growth_3yr_cagr=26.8,
            profit_growth_3yr_cagr=32.4
        ),
        "quarters": FinancialStatement(
            periods=["Dec 2022", "Mar 2023", "Jun 2023", "Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024"],
            rows=[
                FinancialRow(metric="Sales", values={"Dec 2022": 27790, "Mar 2023": 30540, "Jun 2023": 31540, "Sep 2023": 33920, "Dec 2023": 35480, "Mar 2024": 37110, "Jun 2024": 38220, "Sep 2024": 39550, "Dec 2024": 41200}),
                FinancialRow(metric="Expenses", values={"Dec 2022": 14550, "Mar 2023": 16710, "Jun 2023": 17400, "Sep 2023": 19680, "Dec 2023": 20760, "Mar 2024": 21800, "Jun 2024": 22400, "Sep 2024": 23100, "Dec 2024": 24100}),
                FinancialRow(metric="Operating Profit", values={"Dec 2022": 13240, "Mar 2023": 13830, "Jun 2023": 14140, "Sep 2023": 14240, "Dec 2023": 14720, "Mar 2024": 15310, "Jun 2024": 15820, "Sep 2024": 16450, "Dec 2024": 17100}),
                FinancialRow(metric="OPM %", values={"Dec 2022": 47.6, "Mar 2023": 45.3, "Jun 2023": 44.8, "Sep 2023": 42.0, "Dec 2023": 41.5, "Mar 2024": 41.3, "Jun 2024": 41.4, "Sep 2024": 41.6, "Dec 2024": 41.5}),
                FinancialRow(metric="Other Income", values={"Dec 2022": 5020, "Mar 2023": 5120, "Jun 2023": 5420, "Sep 2023": 5830, "Dec 2023": 6120, "Mar 2024": 6500, "Jun 2024": 6450, "Sep 2024": 6800, "Dec 2024": 7200}),
                FinancialRow(metric="Interest", values={"Dec 2022": 11320, "Mar 2023": 12870, "Jun 2023": 13320, "Sep 2023": 15610, "Dec 2023": 16900, "Mar 2024": 17650, "Jun 2024": 18200, "Sep 2024": 18800, "Dec 2024": 19500}),
                FinancialRow(metric="Depreciation", values={"Dec 2022": 410, "Mar 2023": 450, "Jun 2023": 460, "Sep 2023": 480, "Dec 2023": 510, "Mar 2024": 540, "Jun 2024": 560, "Sep 2024": 580, "Dec 2024": 600}),
                FinancialRow(metric="Profit before tax", values={"Dec 2022": 11490, "Mar 2023": 12050, "Jun 2023": 12540, "Sep 2023": 13580, "Dec 2023": 13950, "Mar 2024": 14320, "Jun 2024": 14750, "Sep 2024": 15470, "Dec 2024": 16200}),
                FinancialRow(metric="Tax %", values={"Dec 2022": 24.0, "Mar 2023": 24.0, "Jun 2023": 23.0, "Sep 2023": 24.0, "Dec 2023": 24.0, "Mar 2024": 25.0, "Jun 2024": 25.0, "Sep 2024": 24.0, "Dec 2024": 24.0}),
                FinancialRow(metric="Net Profit", values={"Dec 2022": 8792, "Mar 2023": 9853, "Jun 2023": 10636, "Sep 2023": 10896, "Dec 2023": 11059, "Mar 2024": 11672, "Jun 2024": 11696, "Sep 2024": 12948, "Dec 2024": 13450}),
                FinancialRow(metric="EPS in Rs", values={"Dec 2022": 12.6, "Mar 2023": 14.1, "Jun 2023": 15.2, "Sep 2023": 15.5, "Dec 2023": 15.8, "Mar 2024": 16.6, "Jun 2024": 16.6, "Sep 2024": 18.4, "Dec 2024": 19.1})
            ]
        ),
        "profit_loss": FinancialStatement(
            periods=["Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "TTM"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2018": 54966, "Mar 2019": 63401, "Mar 2020": 74798, "Mar 2021": 79118, "Mar 2022": 86375, "Mar 2023": 109279, "Mar 2024": 143890, "TTM": 156510}),
                FinancialRow(metric="Expenses", values={"Mar 2018": 30262, "Mar 2019": 39967, "Mar 2020": 46698, "Mar 2021": 42724, "Mar 2022": 47163, "Mar 2023": 60237, "Mar 2024": 85850, "TTM": 91700}),
                FinancialRow(metric="Operating Profit", values={"Mar 2018": 24704, "Mar 2019": 23434, "Mar 2020": 28100, "Mar 2021": 36394, "Mar 2022": 39212, "Mar 2023": 49042, "Mar 2024": 58040, "TTM": 64810}),
                FinancialRow(metric="OPM %", values={"Mar 2018": 44.9, "Mar 2019": 37.0, "Mar 2020": 37.6, "Mar 2021": 46.0, "Mar 2022": 45.4, "Mar 2023": 44.9, "Mar 2024": 40.3, "TTM": 41.4}),
                FinancialRow(metric="Other Income", values={"Mar 2018": 17420, "Mar 2019": 14510, "Mar 2020": 16440, "Mar 2021": 18970, "Mar 2022": 21890, "Mar 2023": 23400, "Mar 2024": 25800, "TTM": 27650}),
                FinancialRow(metric="Interest", values={"Mar 2018": 31940, "Mar 2019": 36400, "Mar 2020": 41500, "Mar 2021": 40100, "Mar 2022": 39800, "Mar 2023": 47200, "Mar 2024": 70300, "TTM": 74500}),
                FinancialRow(metric="Depreciation", values={"Mar 2018": 870, "Mar 2019": 980, "Mar 2020": 1150, "Mar 2021": 1280, "Mar 2022": 1450, "Mar 2023": 1650, "Mar 2024": 1980, "TTM": 2280}),
                FinancialRow(metric="Profit before tax", values={"Mar 2018": 10560, "Mar 2019": 7500, "Mar 2020": 14280, "Mar 2021": 24190, "Mar 2022": 31750, "Mar 2023": 43590, "Mar 2024": 53560, "TTM": 62640}),
                FinancialRow(metric="Tax %", values={"Mar 2018": 36.0, "Mar 2019": 42.0, "Mar 2020": 34.0, "Mar 2021": 24.0, "Mar 2022": 26.0, "Mar 2023": 22.0, "Mar 2024": 24.0, "TTM": 24.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2018": 6777, "Mar 2019": 3363, "Mar 2020": 7931, "Mar 2021": 18384, "Mar 2022": 23339, "Mar 2023": 34037, "Mar 2024": 44258, "TTM": 49790}),
                FinancialRow(metric="EPS in Rs", values={"Mar 2018": 10.5, "Mar 2019": 5.2, "Mar 2020": 12.2, "Mar 2021": 26.6, "Mar 2022": 33.6, "Mar 2023": 48.8, "Mar 2024": 63.0, "TTM": 70.8})
            ]
        ),
        "balance_sheet": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2019": 1290, "Mar 2020": 1296, "Mar 2021": 1384, "Mar 2022": 1390, "Mar 2023": 1397, "Mar 2024": 1404}),
                FinancialRow(metric="Reserves", values={"Mar 2019": 107074, "Mar 2020": 115206, "Mar 2021": 146123, "Mar 2022": 168856, "Mar 2023": 198900, "Mar 2024": 238200}),
                FinancialRow(metric="Borrowings", values={"Mar 2019": 165320, "Mar 2020": 162897, "Mar 2021": 91631, "Mar 2022": 107231, "Mar 2023": 119325, "Mar 2024": 148500}),
                FinancialRow(metric="Other Liabilities", values={"Mar 2019": 690450, "Mar 2020": 818500, "Mar 2021": 995400, "Mar 2022": 1138500, "Mar 2023": 1264500, "Mar 2024": 1482000}),
                FinancialRow(metric="Total Liabilities", values={"Mar 2019": 964134, "Mar 2020": 1097899, "Mar 2021": 1234538, "Mar 2022": 1415977, "Mar 2023": 1584122, "Mar 2024": 1870104}),
                FinancialRow(metric="Fixed Assets", values={"Mar 2019": 7931, "Mar 2020": 8410, "Mar 2021": 8878, "Mar 2022": 9374, "Mar 2023": 10600, "Mar 2024": 12400}),
                FinancialRow(metric="CWIP", values={"Mar 2019": 320, "Mar 2020": 350, "Mar 2021": 390, "Mar 2022": 420, "Mar 2023": 510, "Mar 2024": 620}),
                FinancialRow(metric="Investments", values={"Mar 2019": 207733, "Mar 2020": 249531, "Mar 2021": 281287, "Mar 2022": 310241, "Mar 2023": 362326, "Mar 2024": 461200}),
                FinancialRow(metric="Other Assets", values={"Mar 2019": 748150, "Mar 2020": 839608, "Mar 2021": 943983, "Mar 2022": 1095942, "Mar 2023": 1210686, "Mar 2024": 1395884}),
                FinancialRow(metric="Total Assets", values={"Mar 2019": 964134, "Mar 2020": 1097899, "Mar 2021": 1234538, "Mar 2022": 1415977, "Mar 2023": 1584122, "Mar 2024": 1870104})
            ]
        ),
        "cash_flow": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2019": 14200, "Mar 2020": 21500, "Mar 2021": 31400, "Mar 2022": 38900, "Mar 2023": 44800, "Mar 2024": 56200}),
                FinancialRow(metric="Cash from Investing Activity", values={"Mar 2019": -8900, "Mar 2020": -12400, "Mar 2021": -14800, "Mar 2022": -18500, "Mar 2023": -21000, "Mar 2024": -26800}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2019": 1200, "Mar 2020": 1400, "Mar 2021": 1600, "Mar 2022": 1900, "Mar 2023": 2300, "Mar 2024": 2800}),
                FinancialRow(metric="Cash from Financing Activity", values={"Mar 2019": -4200, "Mar 2020": -6800, "Mar 2021": -11200, "Mar 2022": -14500, "Mar 2023": -18200, "Mar 2024": -22400}),
                FinancialRow(metric="Net Cash Flow", values={"Mar 2019": 1100, "Mar 2020": 2300, "Mar 2021": 5400, "Mar 2022": 5900, "Mar 2023": 5600, "Mar 2024": 7000})
            ]
        ),
        "concall_insights": [
            ConcallInsight(
                period="Q3 FY25 (Dec 2024)",
                transcript_url="https://www.screener.in/company/ICICIBANK/consolidated/#documents",
                presentation_url="https://www.screener.in/company/ICICIBANK/consolidated/#documents",
                cfo_and_fcf_analysis="Return on Assets (RoA) remained sector-leading at 2.34% with Return on Equity (RoE) of 18.9%. Net interest margin (NIM) held resilient at 4.27%.",
                demand_drivers=[
                    "Domestic loan portfolio grew 15.2% YoY, led by Business Banking (+31.9% YoY) and SME lending (+23.4% YoY).",
                    "Net NPA declined to just 0.42% with provision coverage ratio (PCR) at a robust 80.4%.",
                    "iMobile Pay and Trade Online platform capturing 75%+ new digital customer onboarding."
                ],
                supply_and_capex=[
                    "Added 140 branches in Q3, taking total branch network to 6,613 branches.",
                    "Cloud migration reaching 65% of enterprise banking core systems."
                ],
                management_guidance="Management reiterated adherence to risk-calibrated operating profit growth within a sustainable 2.2-2.4% RoA corridor and strong capital adequacy (CET-1 at 16.3%).",
                risks_and_headwinds=[
                    "Unsecured personal loan and credit card stress in selected borrower cohorts.",
                    "Liquidity coverage ratio (LCR) regulation revisions by RBI."
                ],
                analyst_sentiment="Bullish - Best-in-class compounding bank with industry-leading RoA, robust asset quality, and stellar execution."
            )
        ],
        "annual_report_insights": [
            AnnualReportInsight(
                year="FY 2024",
                report_url="https://www.screener.in/company/ICICIBANK/consolidated/#documents",
                cfo_fcf_performance="Operating profit was Rs 58,040 Cr. Net profit crossed record Rs 44,258 Cr (+30% YoY).",
                capex_cwip_summary="Tech and branch infrastructure capex of Rs 2,800 Cr.",
                strategic_priorities=[
                    "Scaling 360-degree customer ecosystem across retail, MSME and corporate.",
                    "Expanding granular liability franchise and retail deposits.",
                    "Leveraging AI algorithms for instant credit underwriting."
                ],
                forensic_checklist={
                    "promoter_pledge": "0.0% (Zero promoter pledge, institutional held)",
                    "auditor_qualification": "Unmodified / Clean Audit Report by M S K A & Associates",
                    "related_party_transactions": "Arms-length subsidiary banking contracts",
                    "contingent_liabilities": "Standard banking LC/guarantee commitments"
                }
            )
        ],
        "documents": DocumentLinks(
            annual_reports=[
                {"name": "Annual Report FY24", "url": "https://www.screener.in/company/ICICIBANK/consolidated/#documents"}
            ],
            concalls=[
                {"name": "Q3 FY25 Earnings Call Transcript", "url": "https://www.screener.in/company/ICICIBANK/consolidated/#documents"}
            ],
            presentations=[
                {"name": "Q3 FY25 Investor Presentation", "url": "https://www.screener.in/company/ICICIBANK/consolidated/#documents"}
            ]
        )
    },
    "HINDUNILVR": {
        "symbol": "HINDUNILVR",
        "name": "Hindustan Unilever Ltd",
        "sector": "Consumer Goods / FMCG",
        "industry": "Home Care / Beauty & Personal Care / Foods",
        "about": "Hindustan Unilever Limited is India's largest Fast Moving Consumer Goods company with a heritage of over 90 years. On any given day, nine out of ten Indian households use one or more of its brands like Surf Excel, Dove, Sunsilk, Horlicks, and Lifebuoy.",
        "ratios": KeyRatios(
            market_cap_cr=550000.0,
            current_price=2340.0,
            high_low="2769 / 2170",
            stock_pe=52.4,
            book_value=220.0,
            dividend_yield_pct=1.80,
            roce_pct=26.5,
            roe_pct=20.4,
            face_value=1.0,
            industry_pe=48.0,
            debt_to_equity=0.03,
            interest_coverage=38.0,
            fcf_yield_pct=2.1,
            sales_growth_3yr_cagr=10.5,
            profit_growth_3yr_cagr=7.2
        ),
        "quarters": FinancialStatement(
            periods=["Dec 2022", "Mar 2023", "Jun 2023", "Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024"],
            rows=[
                FinancialRow(metric="Sales", values={"Dec 2022": 15597, "Mar 2023": 15215, "Jun 2023": 15499, "Sep 2023": 15623, "Dec 2023": 15567, "Mar 2024": 15210, "Jun 2024": 15707, "Sep 2024": 15926, "Dec 2024": 16400}),
                FinancialRow(metric="Expenses", values={"Dec 2022": 11899, "Mar 2023": 11644, "Jun 2023": 11832, "Sep 2023": 11728, "Dec 2023": 11847, "Mar 2024": 11620, "Jun 2024": 11950, "Sep 2024": 12150, "Dec 2024": 12450}),
                FinancialRow(metric="Operating Profit", values={"Dec 2022": 3698, "Mar 2023": 3571, "Jun 2023": 3667, "Sep 2023": 3895, "Dec 2023": 3720, "Mar 2024": 3590, "Jun 2024": 3757, "Sep 2024": 3776, "Dec 2024": 3950}),
                FinancialRow(metric="OPM %", values={"Dec 2022": 23.7, "Mar 2023": 23.5, "Jun 2023": 23.7, "Sep 2023": 24.9, "Dec 2023": 23.9, "Mar 2024": 23.6, "Jun 2024": 23.9, "Sep 2024": 23.7, "Dec 2024": 24.1}),
                FinancialRow(metric="Other Income", values={"Dec 2022": 218, "Mar 2023": 204, "Jun 2023": 190, "Sep 2023": 220, "Dec 2023": 240, "Mar 2024": 260, "Jun 2024": 235, "Sep 2024": 250, "Dec 2024": 270}),
                FinancialRow(metric="Interest", values={"Dec 2022": 78, "Mar 2023": 82, "Jun 2023": 80, "Sep 2023": 85, "Dec 2023": 92, "Mar 2024": 95, "Jun 2024": 88, "Sep 2024": 90, "Dec 2024": 85}),
                FinancialRow(metric="Depreciation", values={"Dec 2022": 286, "Mar 2023": 298, "Jun 2023": 305, "Sep 2023": 315, "Dec 2023": 325, "Mar 2024": 340, "Jun 2024": 335, "Sep 2024": 345, "Dec 2024": 355}),
                FinancialRow(metric="Profit before tax", values={"Dec 2022": 3552, "Mar 2023": 3395, "Jun 2023": 3472, "Sep 2023": 3715, "Dec 2023": 3543, "Mar 2024": 3415, "Jun 2024": 3569, "Sep 2024": 3591, "Dec 2024": 3780}),
                FinancialRow(metric="Tax %", values={"Dec 2022": 27.0, "Mar 2023": 24.0, "Jun 2023": 26.0, "Sep 2023": 28.0, "Dec 2023": 29.0, "Mar 2024": 26.0, "Jun 2024": 26.0, "Sep 2024": 27.0, "Dec 2024": 26.0}),
                FinancialRow(metric="Net Profit", values={"Dec 2022": 2581, "Mar 2023": 2601, "Jun 2023": 2556, "Sep 2023": 2657, "Dec 2023": 2509, "Mar 2024": 2561, "Jun 2024": 2612, "Sep 2024": 2595, "Dec 2024": 2795}),
                FinancialRow(metric="EPS in Rs", values={"Dec 2022": 11.0, "Mar 2023": 11.1, "Jun 2023": 10.9, "Sep 2023": 11.3, "Dec 2023": 10.7, "Mar 2024": 10.9, "Jun 2024": 11.1, "Sep 2024": 11.0, "Dec 2024": 11.9})
            ]
        ),
        "profit_loss": FinancialStatement(
            periods=["Mar 2018", "Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "TTM"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2018": 35218, "Mar 2019": 38885, "Mar 2020": 39136, "Mar 2021": 46437, "Mar 2022": 51472, "Mar 2023": 59144, "Mar 2024": 60469, "TTM": 63250}),
                FinancialRow(metric="Expenses", values={"Mar 2018": 27690, "Mar 2019": 30252, "Mar 2020": 29800, "Mar 2021": 34800, "Mar 2022": 39300, "Mar 2023": 45400, "Mar 2024": 46300, "TTM": 48170}),
                FinancialRow(metric="Operating Profit", values={"Mar 2018": 7528, "Mar 2019": 8633, "Mar 2020": 9336, "Mar 2021": 11637, "Mar 2022": 12172, "Mar 2023": 13744, "Mar 2024": 14169, "TTM": 15080}),
                FinancialRow(metric="OPM %", values={"Mar 2018": 21.4, "Mar 2019": 22.2, "Mar 2020": 23.9, "Mar 2021": 25.1, "Mar 2022": 23.6, "Mar 2023": 23.2, "Mar 2024": 23.4, "TTM": 23.8}),
                FinancialRow(metric="Other Income", values={"Mar 2018": 680, "Mar 2019": 760, "Mar 2020": 733, "Mar 2021": 513, "Mar 2022": 444, "Mar 2023": 718, "Mar 2024": 930, "TTM": 1015}),
                FinancialRow(metric="Interest", values={"Mar 2018": 20, "Mar 2019": 28, "Mar 2020": 106, "Mar 2021": 108, "Mar 2022": 98, "Mar 2023": 101, "Mar 2024": 352, "TTM": 358}),
                FinancialRow(metric="Depreciation", values={"Mar 2018": 478, "Mar 2019": 524, "Mar 2020": 938, "Mar 2021": 1012, "Mar 2022": 1025, "Mar 2023": 1030, "Mar 2024": 1285, "TTM": 1370}),
                FinancialRow(metric="Profit before tax", values={"Mar 2018": 7710, "Mar 2019": 8841, "Mar 2020": 9025, "Mar 2021": 11030, "Mar 2022": 11493, "Mar 2023": 13331, "Mar 2024": 13462, "TTM": 14367}),
                FinancialRow(metric="Tax %", values={"Mar 2018": 32.0, "Mar 2019": 32.0, "Mar 2020": 25.0, "Mar 2021": 28.0, "Mar 2022": 24.0, "Mar 2023": 25.0, "Mar 2024": 25.0, "TTM": 26.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2018": 5214, "Mar 2019": 6060, "Mar 2020": 6756, "Mar 2021": 7999, "Mar 2022": 8892, "Mar 2023": 10143, "Mar 2024": 10282, "TTM": 10614}),
                FinancialRow(metric="EPS in Rs", values={"Mar 2018": 24.1, "Mar 2019": 28.0, "Mar 2020": 31.2, "Mar 2021": 34.0, "Mar 2022": 37.8, "Mar 2023": 43.2, "Mar 2024": 43.8, "TTM": 45.2})
            ]
        ),
        "balance_sheet": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2019": 216, "Mar 2020": 216, "Mar 2021": 235, "Mar 2022": 235, "Mar 2023": 235, "Mar 2024": 235}),
                FinancialRow(metric="Reserves", values={"Mar 2019": 7650, "Mar 2020": 8013, "Mar 2021": 47439, "Mar 2022": 48800, "Mar 2023": 50030, "Mar 2024": 51400}),
                FinancialRow(metric="Borrowings", values={"Mar 2019": 0, "Mar 2020": 0, "Mar 2021": 0, "Mar 2022": 0, "Mar 2023": 1200, "Mar 2024": 1500}),
                FinancialRow(metric="Other Liabilities", values={"Mar 2019": 10050, "Mar 2020": 11400, "Mar 2021": 21500, "Mar 2022": 22400, "Mar 2023": 23800, "Mar 2024": 24900}),
                FinancialRow(metric="Total Liabilities", values={"Mar 2019": 17916, "Mar 2020": 19629, "Mar 2021": 69174, "Mar 2022": 71435, "Mar 2023": 75265, "Mar 2024": 78035}),
                FinancialRow(metric="Fixed Assets", values={"Mar 2019": 4800, "Mar 2020": 5500, "Mar 2021": 51200, "Mar 2022": 52100, "Mar 2023": 53400, "Mar 2024": 54200}),
                FinancialRow(metric="CWIP", values={"Mar 2019": 450, "Mar 2020": 580, "Mar 2021": 780, "Mar 2022": 820, "Mar 2023": 950, "Mar 2024": 1100}),
                FinancialRow(metric="Investments", values={"Mar 2019": 2700, "Mar 2020": 3200, "Mar 2021": 3400, "Mar 2022": 3800, "Mar 2023": 4100, "Mar 2024": 4600}),
                FinancialRow(metric="Other Assets", values={"Mar 2019": 9966, "Mar 2020": 10349, "Mar 2021": 13794, "Mar 2022": 14715, "Mar 2023": 16815, "Mar 2024": 18135}),
                FinancialRow(metric="Total Assets", values={"Mar 2019": 17916, "Mar 2020": 19629, "Mar 2021": 69174, "Mar 2022": 71435, "Mar 2023": 75265, "Mar 2024": 78035})
            ]
        ),
        "cash_flow": FinancialStatement(
            periods=["Mar 2019", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2019": 5800, "Mar 2020": 7300, "Mar 2021": 8950, "Mar 2022": 9050, "Mar 2023": 9920, "Mar 2024": 13800}),
                FinancialRow(metric="Cash from Investing Activity", values={"Mar 2019": -1400, "Mar 2020": -1900, "Mar 2021": -2400, "Mar 2022": -1800, "Mar 2023": -2100, "Mar 2024": -2500}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2019": 800, "Mar 2020": 950, "Mar 2021": 1100, "Mar 2022": 1200, "Mar 2023": 1400, "Mar 2024": 1600}),
                FinancialRow(metric="Cash from Financing Activity", values={"Mar 2019": -4300, "Mar 2020": -5200, "Mar 2021": -6400, "Mar 2022": -7200, "Mar 2023": -7800, "Mar 2024": -11100}),
                FinancialRow(metric="Net Cash Flow", values={"Mar 2019": 100, "Mar 2020": 200, "Mar 2021": 150, "Mar 2022": 50, "Mar 2023": 20, "Mar 2024": 200})
            ]
        ),
        "concall_insights": [
            ConcallInsight(
                period="Q3 FY25 (Dec 2024)",
                transcript_url="https://www.screener.in/company/HINDUNILVR/consolidated/#documents",
                presentation_url="https://www.screener.in/company/HINDUNILVR/consolidated/#documents",
                cfo_and_fcf_analysis="Cash conversion remained steady at 102% of PAT. FCF for Q3 stood at Rs 2,400 Cr.",
                demand_drivers=[
                    "Underlying volume growth (UVG) came at 2.5% YoY, with urban premium channels outpacing mass rural demand.",
                    "Home Care delivered 6% revenue growth driven by Surf Excel liquids and Comfort fabric conditioners.",
                    "Beauty & Wellbeing saw strong traction in digital-first acquisitions (Oziva, Simple)."
                ],
                supply_and_capex=[
                    "Demerger / strategic review of the Ice Cream business (Kwality Wall's) initiated to unlock core focus.",
                    "Supply chain automated distribution centers scaling direct retailer connectivity (Shikhar App reaching 1.3M outlets)."
                ],
                management_guidance="Management anticipates gradual rural consumption revival supported by favorable monsoon and government welfare outlays, guiding for low-single digit volume growth and stable OPM.",
                risks_and_headwinds=[
                    "Crude oil derivative (LAB) and palm oil cost inflation putting pressure on gross margins.",
                    "Intense price competition from regional/local soap and detergent players."
                ],
                analyst_sentiment="Neutral / Watchlist - High P/E multiple (52x) vs moderate single-digit volume growth."
            )
        ],
        "annual_report_insights": [
            AnnualReportInsight(
                year="FY 2024",
                report_url="https://www.screener.in/company/HINDUNILVR/consolidated/#documents",
                cfo_fcf_performance="CFO reached Rs 13,800 Cr. Net Free Cash Flow was Rs 12,200 Cr, enabling full dividend distribution.",
                capex_cwip_summary="Capex of Rs 1,600 Cr in digital manufacturing and aerosol deodorant lines.",
                strategic_priorities=[
                    "Premiumization and channel transformation (Quick Commerce, E-comm).",
                    "Separation / value realization of Ice Cream business.",
                    "Accelerating Health & Wellbeing nutrition portfolio."
                ],
                forensic_checklist={
                    "promoter_pledge": "0.0% (Zero pledge)",
                    "auditor_qualification": "Unmodified / Clean Audit Report by B S R & Co.",
                    "related_party_transactions": "Royalty and central technical fees paid to Unilever PLC at board-approved cap",
                    "contingent_liabilities": "National Anti-Profiteering (NAA) tax dispute sub judice"
                }
            )
        ],
        "documents": DocumentLinks(
            annual_reports=[
                {"name": "Annual Report FY24", "url": "https://www.screener.in/company/HINDUNILVR/consolidated/#documents"}
            ],
            concalls=[
                {"name": "Q3 FY25 Earnings Call Transcript", "url": "https://www.screener.in/company/HINDUNILVR/consolidated/#documents"}
            ],
            presentations=[
                {"name": "Q3 FY25 Investor Presentation", "url": "https://www.screener.in/company/HINDUNILVR/consolidated/#documents"}
            ]
        )
    }
}

