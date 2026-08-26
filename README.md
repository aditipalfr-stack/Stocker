# Stocker - Fundamental Stock Screener & Decision Engine (Nifty 500)

**Stocker** is an institutional-grade investment research and decision platform for Indian Equities (starting with Top Market Leaders and scalable to the entire Nifty 500).

Unlike generic screeners that only show pre-calculated trailing ratios, Stocker extracts and models **raw fundamental financial statements** (Quarterly results, P&L, Balance Sheet, Cash Flow), evaluates operational cash conversion, extracts qualitative insights from Concall transcripts & Annual Reports, and provides interactive 5-year forward projection & DCF valuation simulators to discover the **Top 5 High-Conviction Bets**.

---

## Key Features

1. **Raw Screener Financial Statements**:
   - Primary 12-Quarter results, 10-Year Annual P&L, 10-Year Balance Sheet, and 10-Year Cash Flow statements in standard ₹ Cr notation.
   - Comprehensive metric granularity (Operating profit, OPM %, CWIP, Gross block, CFO, Capex, FCF).

2. **QoQ & YoY Momentum & Operating Leverage**:
   - Quarter-on-Quarter (QoQ) and Year-on-Year (YoY) revenue & PAT growth trajectories.
   - Operating Margin (OPM %) expansion/contraction trends.
   - 3-Year, 5-Year, and 10-Year historical CAGRs.

3. **Cash Flow & Earnings Quality Engine**:
   - Cumulative 5-Year PAT vs Cumulative CFO conversion (validating whether accounting profit is backed by real cash).
   - Free Cash Flow (FCF = CFO - Capex) and FCF Yield % computation.
   - Balance Sheet Capital Work in Progress (CWIP) as % of Net Block (flagging upcoming capacity commissioning triggers).

4. **Interactive 5-Year Projections & DCF Valuation Simulator**:
   - Real-time slider controls for **Expected Revenue CAGR %**, **Target OPM %**, **Capex % of Sales**, and **Target Exit P/E Multiple**.
   - Live **DCF Fair Value per share**, **Margin of Safety %**, and **3-Year Projected CAGR / IRR %**.
   - Instant scenario toggles (`Bull Case`, `Base Case`, `Bear Case`).

5. **Concall & Annual Report Qualitative Intelligence**:
   - **CFO & FCF Deep-Dive**: How did the company fare on operational cash generation? Where did the cash go?
   - **Demand Drivers**: Volume growth, market share shifts, pricing power, order book size.
   - **Supply Dynamics & Capex**: CWIP execution status, new plant commissioning dates, supply chain dependencies.
   - **Management Guidance**: Explicit revenue, margin, and volume targets.
   - **Forensic Governance Checklist**: Promoter pledging (0%), clean auditor opinions, related party transactions.
   - **Direct Document Access**: Direct links to open original Annual Reports, Transcripts, and Investor PPTs.

6. **5-Pillar Decision Engine & Top 5 Conviction Generator**:
   - Scores companies (0-100) across:
     - Growth Momentum (20%)
     - Cash Flow Quality & FCF Strength (25%)
     - Capital Efficiency & Moat (ROCE/ROE) (20%)
     - Balance Sheet Safety & CWIP Trigger (15%)
     - Valuation Margin of Safety (20%)
   - Automatically ranks the universe and generates synthesized investment theses for the **Top 5 Best Bets**.

7. **Side-by-Side Comparison Arena**:
   - Compare 2 to 5 stocks simultaneously on metrics, valuation, cash conversion, and factor score breakdowns.

8. **On-Demand Screener Ingestion**:
   - Search bar allows adding any ticker from Nifty 500 (e.g. `TITAN`, `DIXON`, `POLYCAB`, `TRENT`, `BEL`, etc.) directly from Screener.in on the fly with local caching.

---

### 1. Configure Environment (Optional but Recommended for Live AI Document Intelligence)
Copy the template `.env.example` to `.env`:
```bash
cp .env.example .env
```
Add your preferred API key (Google Gemini is preferred):
```bash
GEMINI_API_KEY=your_gemini_api_key_here
# OR
OPENAI_API_KEY=your_openai_api_key_here
```
*(Note: If no API key is provided, the platform continues working normally and displays verified demo/baseline intelligence with clear status indicators).*

### 2. Launch Platform
Simply run the startup script:
```bash
./start.sh
```
This launches:
- **Backend API & Web App**: `http://localhost:8088` (FastAPI + Swagger Docs at `/docs`)
- **Frontend Dashboard**: `http://localhost:5188` (React + Tailwind CSS + Recharts)

To run on custom ports:
```bash
BACKEND_PORT=9000 FRONTEND_PORT=3000 ./start.sh
```

### 3. Run Automated Test Suite
```bash
PYTHONPATH=libs:backend python3 backend/tests.py
```

---

## Business Outlook & Document Intelligence Pipeline

The **Business Outlook** tab extracts and verifies fundamental claims directly from corporate concall transcripts, investor presentations, and annual reports without manual pre-filling:

1. **What Changed Recently**: Fast synthesis of the latest operational updates.
2. **Plan vs Reality**: Cross-period audit comparing historical management guidance ($T-1$) with actual delivery ($T$), classified into `Delivered`, `In Progress`, `Delayed`, `Missed`.
3. **Growth Pipeline**: Capacity expansions, new plants, capex projects, and acquisitions with verifiable COD timelines.
4. **Demand & Orders**: Order backlog / TCV, subscriber additions, volume/pricing mix, and segment momentum.
5. **Cash & Problems**: Working capital cycle, inventory turns, debt trajectory, and independent mathematical cross-checks.

---

## Technology Stack

- **Backend**: Python 3.12, FastAPI, BeautifulSoup4, pypdf, python-dotenv, Pydantic, Uvicorn
- **AI Service**: Google Gemini (`gemini-2.0-flash`) / OpenAI (`gpt-4o-mini`)
- **Frontend**: React 19, Vite, TypeScript, Tailwind CSS, Lucide Icons, Recharts


