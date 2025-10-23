# Clinical Trial Data Analyzer

A comprehensive Python application that processes clinical trial patient data and generates detailed statistical analysis with interactive visualizations.


## Getting Started

1. Clone this repository
2. Follow "How to Run" section above
3. Choose your execution mode:
   - Console for quick analysis
   - Web for interactive exploration
   - API for programmatic integration
4. Review `trial_results.json` for statistics
5. Check `trial_data.db` for persistent data



## How to Run the Application

### Prerequisites
- Python 3.8 or higher
- Git (for cloning the repository)

### Step-by-Step Installation

1. **Clone the repository**
```bash
   git clone https://github.com/YOUR-USERNAME/clinical-trial-analyzer.git
   cd clinical-trial-analyzer
```

2. **Create a virtual environment**
```bash
   python3 -m venv venv
```

3. **Activate the virtual environment**
   
   **On Mac/Linux:**
```bash
   source venv/bin/activate
```
   
   **On Windows:**
```bash
   venv\Scripts\activate
```

4. **Install dependencies**
```bash
   pip install -r requirements.txt
```

### Running the Application

The application supports three execution modes:

#### Mode 1: Console Output (Quick Analysis)
```bash
python clinical_trial_analyzer.py
```

**Output:**
- Formatted report printed to console
- Statistics saved to `trial_results.json`
- Data persisted in `trial_data.db` SQLite database

#### Mode 2: Web Dashboard (Interactive)
```bash
python clinical_trial_analyzer.py web
```

Then open your browser and navigate to: `http://localhost:5000`

**Features:**
- Upload CSV file for analysis
- View summary statistics (4 stat cards)
- Breakdown by trial site
- Interactive Plotly charts
- Real-time data processing

**To stop the server:** Press `Control+C` in Terminal

#### Mode 3: REST API (For Integration)
```bash
python clinical_trial_analyzer.py web
```

In another Terminal:
```bash
curl -F "file=@trial_data.csv" http://localhost:5000/api/analyze
```

**Response:** JSON with all statistics

---

## Dependencies & Why They Were Used

### Required Packages

| Package | Version | Purpose | Efficiency Advantage |
|---------|---------|---------|----------------------|
| **pandas** | 2.0.3 | CSV parsing & data validation | 250% faster than standard CSV module; vectorized operations eliminate Python loops |
| **numpy** | 1.24.3 | Numerical computations & statistical analysis | 10-100x faster than Python loops for calculations |
| **flask** | 2.3.2 | Web server, REST API, routing | Lightweight framework with zero boilerplate; built-in request handling |
| **plotly** | 5.14.0 | Interactive data visualizations | 4x less code vs matplotlib; HTML-embedded charts; interactive features (zoom, pan, hover) |

### Why Not Standard Library Only?

- **CSV Module:** Requires manual validation loops (slow for data processing); no built-in type checking
- **No Built-in Web Framework:** Standard library has no lightweight web solution; Flask provides routing and templating
- **Tkinter Charts:** Basic, not interactive; Plotly provides professional, publication-quality visualizations
- **No Data Processing:** NumPy/Pandas vectorization is essential for fast, scalable analysis

---

## Core Requirements (All Completed)

### 1. Data Processing
- **CSV Parsing:** Reads CSV files with pandas (fast, reliable)
- **Type Validation:** Validates all 6 columns (patient_id, trial_site, enrollment_date, age, adverse_event, completed_trial)
- **Error Handling:** 
  - Invalid dates caught (must be YYYY-MM-DD format)
  - Non-numeric ages flagged and skipped
  - Age range validation (0-150 years)
  - Missing required fields detected
  - Invalid records logged but processing continues (non-fatal errors)

### 2. Generate Summary Statistics
All 6 required metrics calculated and output:

1. **Total Patients Enrolled** - Count of all valid records
2. **Patients Per Trial Site** - Breakdown by Boston, Chicago, Los Angeles, Miami, New York
3. **Average Age** - Mean age of all enrolled patients
4. **Completion Rate** - Percentage of patients who completed the trial
5. **Adverse Event Rate** - Percentage of patients who experienced adverse events
6. **Completion by Adverse Event Status:**
   - Completion rate for patients WITH adverse events
   - Completion rate for patients WITHOUT adverse events

### 3. Output Results 
Multiple formats provided:

- **Console Report:** Formatted text output to Terminal (human-readable)
- **JSON File:** Machine-readable statistics in `trial_results.json`
- **Web Dashboard:** Interactive HTML interface with charts
- **REST API:** JSON endpoint for programmatic access
- **Screenshots:** Included in documentation

---

##  Bonus Features (All 5 Implemented)

### Option A: Web Interface
**Status:** Fully Implemented

- File upload form for CSV selection
- Real-time data processing
- 4 Summary Statistics cards (Total Patients, Average Age, Completion Rate, Adverse Event Rate)
- Patients per site breakdown table
- Completion rate comparison (with vs without adverse events)
- Responsive HTML design with gradient styling
- Error handling with user-friendly messages

**Access:** Run `python clinical_trial_analyzer.py web` and visit `http://localhost:5000`

### Option B: REST API Endpoint 
**Status:** Fully Implemented

- **POST /api/analyze** - Upload CSV file and receive JSON statistics
```bash
  curl -F "file=@trial_data.csv" http://localhost:5000/api/analyze
```
  
- **GET /api/health** - Health check endpoint
```bash
  curl http://localhost:5000/api/health
```

- Error handling with descriptive messages
- JSON request/response format
- Usage documentation in code comments

### Option C: Data Visualization
**Status:** Fully Implemented with 4 Interactive Charts

1. **Patient Enrollment Over Time** (Line Chart)
   - Shows enrollment trends across the study period
   - X-axis: Enrollment dates
   - Y-axis: New enrollments per time period

2. **Completion by Trial Site** (Stacked Bar Chart)
   - Visualizes completion rates per site
   - Blue: Completed trials
   - Red: Incomplete trials
   - Shows which sites perform best

3. **Age Distribution** (Histogram)
   - Shows patient age demographics
   - Identifies age clustering patterns
   - Useful for understanding population characteristics

4. **Adverse Event Distribution** (Pie Chart)
   - Shows proportion of patients with/without adverse events
   - Percentage breakdown displayed
   - Quick visual summary of safety profile

**All Charts:**
- Interactive (zoom, pan, hover for details)
- Embedded in web dashboard
- Powered by Plotly for professional rendering
- Responsive and mobile-friendly

### Option D: Advanced Analysis 
**Status:** Fully Implemented

- **Site Performance Analysis:** Ranking sites by completion rates, adverse event rates, average age
- **Age Group Analysis:** Bucketing patients by age ranges (<30, 30-39, 40-49, 50-59, 60+) with completion metrics
- **Correlation Analysis:** Identifying relationships between variables (age ↔ completion, adverse events ↔ completion, etc.)
- **Actionable Insights:** Extraction of meaningful patterns and trends

**Implementation:**
```python
def get_advanced_analysis(self) -> Dict:
    # Site performance analysis
    # Age group bucketing with completion rates
    # Correlation matrix calculation
    return analysis_results
```

### Option E: Database Integration
**Status:** Fully Implemented

- **SQLite Database:** Auto-created from CSV data (`trial_data.db`)
- **Persistent Storage:** All patient records stored and queryable
- **Schema:** Single `patients` table with 6 columns matching CSV structure
- **Query Capability:** Full SQL query support for advanced analysis

**How It Works:**
```python
def load_to_sqlite(self):
    # Converts DataFrame to SQLite table
    # Automatically runs after CSV processing
    # Enables persistent storage for future analysis
```

**Example Usage:**
```bash
sqlite3 trial_data.db
SELECT trial_site, COUNT(*) as total, SUM(completed_trial) as completed 
FROM patients GROUP BY trial_site;
```

---

## Sample Data

**File:** `trial_data.csv`

- **Records:** 30 patient records (exceeds 20-30 requirement)
- **Trial Sites:** 5 locations
  - Boston: 6 patients (100% completion, no adverse events)
  - Chicago: 6 patients (33% completion, 100% adverse events)
  - Los Angeles: 6 patients (100% completion, no adverse events)
  - Miami: 6 patients (0% completion, 100% adverse events)
  - New York: 6 patients (80% completion, mixed adverse events)
- **Date Range:** January 10, 2024 - March 28, 2024
- **Age Range:** 29-62 years
- **Realistic Patterns:** Clear correlation between adverse events and completion rates

Data is synthetically generated for demonstration but follows realistic trial patterns.

---

## 📈 Sample Output

### Console Output
```
======================================================================
CLINICAL TRIAL DATA SUMMARY REPORT
======================================================================

ENROLLMENT SUMMARY
  Total Patients Enrolled: 30

PATIENTS PER TRIAL SITE
  Boston: 6
  Chicago: 6
  Los Angeles: 6
  Miami: 6
  New York: 6

DEMOGRAPHICS
  Average Age: 45.37 years

TRIAL OUTCOMES
  Completion Rate: 63.33%
  Adverse Event Rate: 46.67%

OUTCOME COMPARISON
  Completion Rate (with adverse events): 21.43%
  Completion Rate (without adverse events): 100.0%

DATA QUALITY
  Valid Records: 30
  Invalid Records: 0
======================================================================
```

### JSON Output (trial_results.json)
```json
{
  "total_patients": 30,
  "patients_per_site": {
    "Boston": 6,
    "Chicago": 6,
    "Los Angeles": 6,
    "Miami": 6,
    "New York": 6
  },
  "average_age": 45.37,
  "completion_rate_percent": 63.33,
  "adverse_event_rate_percent": 46.67,
  "completion_rate_with_adverse_percent": 21.43,
  "completion_rate_without_adverse_percent": 100.0,
  "data_quality": {
    "valid_records": 30,
    "invalid_records": 0
  }
}
```

### Web Dashboard
- Summary statistics cards with metrics
- Trial site breakdown
- 4 interactive Plotly charts
- File upload functionality
- Real-time processing

*Screenshots available in project documentation*

---

##  Project Structure
```
clinical-trial-analyzer/
├── clinical_trial_analyzer.py    # Main application (500+ lines)
│   ├── TrialDataAnalyzer class
│   ├── Flask web server setup
│   ├── REST API endpoints
│   ├── HTML dashboard template
│   └── main() console execution
├── trial_data.csv                # Sample dataset (30 records)
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── .gitignore                    # Git configuration
├── venv/                         # Virtual environment (not committed)
├── trial_results.json            # Output (generated)
└── trial_data.db                 # SQLite database (generated)
```

---

##  Design Decisions

### Architecture Choice: Single File Application
- **Reasoning:** All functionality (data processing, web server, API, visualization) in one file for easy deployment
- **Benefit:** No complex project structure for a junior exercise; code is easy to follow
- **Trade-off:** Not ideal for massive applications, but perfect for this scope

### Class-Based Design with TrialDataAnalyzer
- **Reasoning:** Encapsulates all data processing logic; promotes reusability
- **Methods:**
  - `load_and_validate_data()` - CSV parsing with validation
  - `calculate_statistics()` - All metric calculations
  - `generate_text_report()` - Formatted console output
  - `export_to_json()` - JSON serialization
  - `load_to_sqlite()` - Database persistence
  - `create_visualizations()` - Plotly chart generation
  - `get_advanced_analysis()` - Trend and pattern analysis

### Multiple Execution Modes
- **Reasoning:** Different use cases (quick analysis, interactive exploration, programmatic access)
- **Implementation:** Single codebase, three different entry points

### Non-Fatal Error Handling
- **Reasoning:** Invalid records don't crash the application; processing continues
- **Benefit:** Maximizes data extraction while maintaining data quality
- **Implementation:** Invalid rows logged separately; valid rows processed normally

---

## Assumptions & Validation Rules

1. **Date Format:** All enrollment dates expected in YYYY-MM-DD (ISO 8601) format
2. **Age Validity:** Ages outside 0-150 range considered invalid
3. **Boolean Fields:** Case-insensitive; accepts "true"/"false" or "1"/"0"
4. **File Encoding:** UTF-8 assumed for all CSV files
5. **Trial Site Names:** No validation applied; any string accepted
6. **Demographics:** Average age calculated across all enrolled patients regardless of completion status

---

##️ Time Estimate

**Total Development Time: 3.5 hours**

- Requirements analysis & planning: 0.5 hours
- Core implementation (data processing, statistics): 1.0 hour
- Bonus features (web, API, charts, analysis, DB): 1.5 hours
- Testing & documentation: 0.5 hours

---

## Testing

Application tested with:
- Valid CSV files with all required fields 
- Various data ranges (ages 29-62, 5 trial sites, 30 records) 
- Edge cases (100% completion sites, 0% completion sites, heavy adverse events) 
- Error scenarios (invalid dates, non-numeric ages, missing fields) 
- Multiple input methods (console, web upload, API) 

---

## Code Quality

- **Readability:** Clear variable names, logical method organization
- **Organization:** Single class encapsulating all logic
- **Type Hints:** Methods include input/output type annotations
- **Comments:** Docstrings on all methods; inline comments for complex logic
- **Error Handling:** Comprehensive validation with specific error messages
- **Best Practices:** PEP 8 compliant, DRY principle applied

---

