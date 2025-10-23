import pandas as pd
import numpy as np
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, Tuple


class TrialDataAnalyzer:
    """Processes clinical trial data and generates analysis."""
    
    def __init__(self, csv_file: str):
        self.csv_file = csv_file
        self.df = None
        self.invalid_records = []
        self.errors = []
        self.db_path = "trial_data.db"
    
    def load_and_validate_data(self) -> bool:
        """
        Load CSV and validate data using pandas.
        Returns: bool indicating success
        """
        try:
            # Read CSV with pandas (more efficient than csv module for validation)
            self.df = pd.read_csv(self.csv_file)
            
            # Validate required columns
            required_cols = ['patient_id', 'trial_site', 'enrollment_date', 
                           'age', 'adverse_event', 'completed_trial']
            missing_cols = [col for col in required_cols if col not in self.df.columns]
            if missing_cols:
                self.errors.append(f"Missing columns: {missing_cols}")
                return False
            
            # Data type conversions and validation
            original_len = len(self.df)
            
            # Convert and validate
            self.df['enrollment_date'] = pd.to_datetime(self.df['enrollment_date'], 
                                                         format='%Y-%m-%d', errors='coerce')
            self.df['age'] = pd.to_numeric(self.df['age'], errors='coerce')
            self.df['adverse_event'] = self.df['adverse_event'].astype(str).str.lower().isin(['true', '1'])
            self.df['completed_trial'] = self.df['completed_trial'].astype(str).str.lower().isin(['true', '1'])
            
            # Flag invalid rows
            invalid_mask = (
                self.df['enrollment_date'].isna() |
                self.df['age'].isna() |
                (self.df['age'] < 0) |
                (self.df['age'] > 150) |
                self.df['patient_id'].isna() |
                self.df['trial_site'].isna()
            )
            
            self.invalid_records = self.df[invalid_mask].to_dict('records')
            if len(self.invalid_records) > 0:
                self.errors.append(f"Found {len(self.invalid_records)} invalid records")
            
            # Keep only valid records
            self.df = self.df[~invalid_mask].reset_index(drop=True)
            
            if len(self.df) == 0:
                self.errors.append("No valid records found after validation")
                return False
            
            return True
            
        except Exception as e:
            self.errors.append(f"Error loading CSV: {str(e)}")
            return False
    
    def calculate_statistics(self) -> Dict:
        """Calculate all summary statistics using pandas (vectorized operations)."""
        if self.df is None or len(self.df) == 0:
            return {}
        
        total_patients = len(self.df)
        
        stats = {
            'total_patients': total_patients,
            'patients_per_site': self.df['trial_site'].value_counts().to_dict(),
            'average_age': round(self.df['age'].mean(), 2),
            'completion_rate_percent': round((self.df['completed_trial'].sum() / total_patients) * 100, 2),
            'adverse_event_rate_percent': round((self.df['adverse_event'].sum() / total_patients) * 100, 2),
        }
        
        # Completion rates by adverse event status
        with_adverse = self.df[self.df['adverse_event']]
        without_adverse = self.df[~self.df['adverse_event']]
        
        stats['completion_rate_with_adverse_percent'] = (
            round((with_adverse['completed_trial'].sum() / len(with_adverse)) * 100, 2)
            if len(with_adverse) > 0 else 0
        )
        stats['completion_rate_without_adverse_percent'] = (
            round((without_adverse['completed_trial'].sum() / len(without_adverse)) * 100, 2)
            if len(without_adverse) > 0 else 0
        )
        
        stats['data_quality'] = {
            'valid_records': total_patients,
            'invalid_records': len(self.invalid_records)
        }
        
        return stats
    
    def generate_text_report(self) -> str:
        """Generate formatted text report."""
        stats = self.calculate_statistics()
        
        if not stats:
            return "No valid data to report."
        
        report = []
        report.append("=" * 70)
        report.append("CLINICAL TRIAL DATA SUMMARY REPORT")
        report.append("=" * 70)
        report.append("")
        
        report.append("ENROLLMENT SUMMARY")
        report.append(f"  Total Patients Enrolled: {stats['total_patients']}")
        report.append("")
        
        report.append("PATIENTS PER TRIAL SITE")
        for site, count in sorted(stats['patients_per_site'].items()):
            report.append(f"  {site}: {count}")
        report.append("")
        
        report.append("DEMOGRAPHICS")
        report.append(f"  Average Age: {stats['average_age']} years")
        report.append("")
        
        report.append("TRIAL OUTCOMES")
        report.append(f"  Completion Rate: {stats['completion_rate_percent']}%")
        report.append(f"  Adverse Event Rate: {stats['adverse_event_rate_percent']}%")
        report.append("")
        
        report.append("OUTCOME COMPARISON")
        report.append(f"  Completion Rate (with adverse events): {stats['completion_rate_with_adverse_percent']}%")
        report.append(f"  Completion Rate (without adverse events): {stats['completion_rate_without_adverse_percent']}%")
        report.append("")
        
        report.append("DATA QUALITY")
        report.append(f"  Valid Records: {stats['data_quality']['valid_records']}")
        report.append(f"  Invalid Records: {stats['data_quality']['invalid_records']}")
        
        if self.errors:
            report.append("")
            report.append("VALIDATION NOTES")
            for error in self.errors[:5]:
                report.append(f"  - {error}")
        
        report.append("=" * 70)
        return "\n".join(report)
    
    def export_to_json(self, output_file: str = "trial_results.json"):
        """Export statistics to JSON."""
        stats = self.calculate_statistics()
        with open(output_file, 'w') as f:
            json.dump(stats, f, indent=2)
        print(f"JSON exported to {output_file}")
    
    def load_to_sqlite(self):
        """Load data into SQLite database (Bonus E)."""
        try:
            conn = sqlite3.connect(self.db_path)
            self.df.to_sql('patients', conn, if_exists='replace', index=False)
            conn.close()
            print(f"Data loaded to SQLite: {self.db_path}")
        except Exception as e:
            self.errors.append(f"SQLite error: {str(e)}")
    
    def query_sqlite(self, query: str):
        """Query SQLite database."""
        try:
            conn = sqlite3.connect(self.db_path)
            result = pd.read_sql_query(query, conn)
            conn.close()
            return result
        except Exception as e:
            self.errors.append(f"Query error: {str(e)}")
            return None
    
    def get_advanced_analysis(self) -> Dict:
        """Advanced analysis: trends and patterns (Bonus D)."""
        if self.df is None or len(self.df) == 0:
            return {}
        
        # Site performance analysis
        site_analysis = self.df.groupby('trial_site').agg({
            'completed_trial': ['sum', 'count', lambda x: (x.sum()/len(x)*100)],
            'adverse_event': ['sum', lambda x: (x.sum()/len(x)*100)],
            'age': ['mean', 'min', 'max']
        }).round(2)
        
        # Age group analysis
        age_bins = [0, 30, 40, 50, 60, 150]
        age_labels = ['<30', '30-39', '40-49', '50-59', '60+']
        self.df['age_group'] = pd.cut(self.df['age'], bins=age_bins, labels=age_labels)
        
        age_analysis = self.df.groupby('age_group').agg({
            'completed_trial': ['sum', 'count', lambda x: (x.sum()/len(x)*100)],
            'adverse_event': lambda x: (x.sum()/len(x)*100)
        }).round(2)
        
        # Correlation analysis
        correlation = self.df[['age', 'adverse_event', 'completed_trial']].astype(int).corr()
        
        return {
            'site_performance': site_analysis.to_dict(),
            'age_group_analysis': age_analysis.to_dict(),
            'correlation': correlation.to_dict()
        }
    
    def create_visualizations(self) -> Dict[str, str]:
        """Create interactive Plotly visualizations (Bonus C)."""
        if self.df is None or len(self.df) == 0:
            return {}
        
        charts = {}
        
        # 1. Enrollment over time
        enrollment_trend = self.df.groupby('enrollment_date').size().reset_index(name='count')
        fig1 = px.line(enrollment_trend, x='enrollment_date', y='count',
                      title='Patient Enrollment Over Time',
                      labels={'enrollment_date': 'Date', 'count': 'New Enrollments'})
        charts['enrollment_trend'] = fig1.to_html(full_html=False)
        
        # 2. Site comparison
        site_stats = self.df.groupby('trial_site').agg({
            'completed_trial': 'sum',
            'patient_id': 'count'
        }).reset_index()
        site_stats.columns = ['trial_site', 'completed', 'total']
        site_stats['completion_rate'] = (site_stats['completed'] / site_stats['total'] * 100).round(2)
        
        fig2 = px.bar(site_stats, x='trial_site', y=['completed', 'total'],
                     title='Completion by Trial Site',
                     labels={'trial_site': 'Trial Site', 'value': 'Count'})
        charts['site_comparison'] = fig2.to_html(full_html=False)
        
        # 3. Age distribution
        fig3 = px.histogram(self.df, x='age', nbins=15,
                           title='Age Distribution',
                           labels={'age': 'Age', 'count': 'Frequency'})
        charts['age_distribution'] = fig3.to_html(full_html=False)
        
        # 4. Adverse events pie chart
        adverse_counts = self.df['adverse_event'].value_counts()
        fig4 = px.pie(values=adverse_counts.values, names=['No Adverse Events', 'Adverse Events'],
                     title='Adverse Event Distribution')
        charts['adverse_events'] = fig4.to_html(full_html=False)
        
        return charts


# REST API (Bonus B)
app = Flask(__name__)

@app.route('/api/analyze', methods=['POST'])
def analyze_csv():
    """REST API endpoint for CSV analysis."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        file.save('temp_upload.csv')
        
        analyzer = TrialDataAnalyzer('temp_upload.csv')
        if not analyzer.load_and_validate_data():
            return jsonify({'error': 'Failed to load data', 'errors': analyzer.errors}), 400
        
        stats = analyzer.calculate_statistics()
        return jsonify(stats), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'}), 200


# Web Interface (Bonus A)
@app.route('/', methods=['GET', 'POST'])
def dashboard():
    """Web dashboard for viewing trial statistics."""
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template_string(HTML_TEMPLATE, error='No file provided')
        
        file = request.files['file']
        file.save('temp_upload.csv')
        
        analyzer = TrialDataAnalyzer('temp_upload.csv')
        if not analyzer.load_and_validate_data():
            return render_template_string(HTML_TEMPLATE, 
                                        error=f"Validation failed: {', '.join(analyzer.errors)}")
        
        stats = analyzer.calculate_statistics()
        visualizations = analyzer.create_visualizations()
        advanced = analyzer.get_advanced_analysis()
        
        return render_template_string(HTML_TEMPLATE, 
                                     stats=stats,
                                     visualizations=visualizations,
                                     advanced=advanced)
    
    return render_template_string(HTML_TEMPLATE)


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Clinical Trial Data Analyzer</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        .header { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .stat-value { font-size: 28px; font-weight: bold; }
        .stat-label { font-size: 12px; opacity: 0.9; }
        .upload-section { background: #f9f9f9; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .chart-section { margin: 30px 0; background: white; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
        .error { color: #d32f2f; background: #ffebee; padding: 10px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="header">Clinical Trial Data Analyzer</h1>
        
        <div class="upload-section">
            <h3>Upload CSV File</h3>
            <form method="post" enctype="multipart/form-data">
                <input type="file" name="file" accept=".csv" required>
                <button type="submit" style="padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">Analyze</button>
            </form>
        </div>
        
        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}
        
        {% if stats %}
            <h2>Summary Statistics</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{{ stats.total_patients }}</div>
                    <div class="stat-label">Total Patients</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{ stats.average_age }}</div>
                    <div class="stat-label">Average Age</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{ stats.completion_rate_percent }}%</div>
                    <div class="stat-label">Completion Rate</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{ stats.adverse_event_rate_percent }}%</div>
                    <div class="stat-label">Adverse Event Rate</div>
                </div>
            </div>
            
            <h3>Patients Per Site</h3>
            <ul>
                {% for site, count in stats.patients_per_site.items() %}
                    <li>{{ site }}: {{ count }}</li>
                {% endfor %}
            </ul>
            
            <h3>Completion by Adverse Event Status</h3>
            <p>With Adverse Events: {{ stats.completion_rate_with_adverse_percent }}%</p>
            <p>Without Adverse Events: {{ stats.completion_rate_without_adverse_percent }}%</p>
            
            {% if visualizations %}
                <h2>Data Visualizations</h2>
                {% if visualizations.enrollment_trend %}
                    <div class="chart-section">
                        {{ visualizations.enrollment_trend | safe }}
                    </div>
                {% endif %}
                {% if visualizations.site_comparison %}
                    <div class="chart-section">
                        {{ visualizations.site_comparison | safe }}
                    </div>
                {% endif %}
                {% if visualizations.age_distribution %}
                    <div class="chart-section">
                        {{ visualizations.age_distribution | safe }}
                    </div>
                {% endif %}
                {% if visualizations.adverse_events %}
                    <div class="chart-section">
                        {{ visualizations.adverse_events | safe }}
                    </div>
                {% endif %}
            {% endif %}
        {% endif %}
    </div>
</body>
</html>
'''


def main():
    """Main entry point for console execution."""
    analyzer = TrialDataAnalyzer('trial_data.csv')
    
    if analyzer.load_and_validate_data():
        # Core functionality
        print(analyzer.generate_text_report())
        analyzer.export_to_json()
        analyzer.load_to_sqlite()
        
        print("\n" + "="*70)
        print("ADVANCED ANALYSIS - TRENDS AND PATTERNS")
        print("="*70)
        
        advanced = analyzer.get_advanced_analysis()
        
        print("\nSITE PERFORMANCE RANKING:")
        print("-" * 70)
        site_data = analyzer.query_sqlite("""
            SELECT 
                trial_site,
                COUNT(*) as total_patients,
                SUM(completed_trial) as completed,
                ROUND(100.0 * SUM(completed_trial) / COUNT(*), 2) as completion_rate,
                SUM(adverse_event) as adverse_count,
                ROUND(100.0 * SUM(adverse_event) / COUNT(*), 2) as adverse_rate,
                ROUND(AVG(age), 2) as avg_age
            FROM patients
            GROUP BY trial_site
            ORDER BY completion_rate DESC
        """)
        
        if site_data is not None:
            for idx, row in site_data.iterrows():
                print(f"  {row['trial_site']:15} | Completion: {row['completion_rate']:6.2f}% | "
                      f"Adverse Events: {row['adverse_rate']:6.2f}% | Avg Age: {row['avg_age']:5.1f}")
        
        # AGE GROUP ANALYSIS
        print("\n" + "-" * 70)
        print("AGE GROUP ANALYSIS:")
        print("-" * 70)
        
        age_groups = analyzer.query_sqlite("""
            SELECT 
                CASE 
                    WHEN age < 30 THEN '<30'
                    WHEN age < 40 THEN '30-39'
                    WHEN age < 50 THEN '40-49'
                    WHEN age < 60 THEN '50-59'
                    ELSE '60+'
                END as age_group,
                COUNT(*) as total,
                SUM(completed_trial) as completed,
                ROUND(100.0 * SUM(completed_trial) / COUNT(*), 2) as completion_rate,
                ROUND(100.0 * SUM(adverse_event) / COUNT(*), 2) as adverse_rate
            FROM patients
            GROUP BY age_group
            ORDER BY age_group
        """)
        
        if age_groups is not None:
            for idx, row in age_groups.iterrows():
                print(f"  Age {row['age_group']:6} | Completion: {row['completion_rate']:6.2f}% | "
                      f"Adverse Events: {row['adverse_rate']:6.2f}% | Sample Size: {row['total']}")
        
        # CORRELATION INSIGHTS
        print("\n" + "-" * 70)
        print("KEY INSIGHTS:")
        print("-" * 70)
        
        # Adverse events impact
        adverse_impact = analyzer.query_sqlite("""
            SELECT 
                adverse_event,
                COUNT(*) as count,
                SUM(completed_trial) as completed,
                ROUND(100.0 * SUM(completed_trial) / COUNT(*), 2) as completion_rate
            FROM patients
            GROUP BY adverse_event
        """)
        
        if adverse_impact is not None:
            with_adverse = adverse_impact[adverse_impact['adverse_event'] == 1]['completion_rate'].values
            without_adverse = adverse_impact[adverse_impact['adverse_event'] == 0]['completion_rate'].values
            
            if len(with_adverse) > 0 and len(without_adverse) > 0:
                impact_difference = without_adverse[0] - with_adverse[0]
                print(f"  Adverse Event Impact: Patients WITHOUT adverse events are {impact_difference:.1f}% "
                      f"more likely to complete")
        
        # Best and worst performing sites
        best_site = analyzer.query_sqlite("""
            SELECT trial_site, 
                   ROUND(100.0 * SUM(completed_trial) / COUNT(*), 2) as completion_rate
            FROM patients
            GROUP BY trial_site
            ORDER BY completion_rate DESC
            LIMIT 1
        """)
        
        worst_site = analyzer.query_sqlite("""
            SELECT trial_site, 
                   ROUND(100.0 * SUM(completed_trial) / COUNT(*), 2) as completion_rate
            FROM patients
            GROUP BY trial_site
            ORDER BY completion_rate ASC
            LIMIT 1
        """)
        
        if best_site is not None and len(best_site) > 0:
            print(f"  Best Performing Site: {best_site.iloc[0]['trial_site']} "
                  f"({best_site.iloc[0]['completion_rate']:.1f}% completion)")
        
        if worst_site is not None and len(worst_site) > 0:
            print(f"  Worst Performing Site: {worst_site.iloc[0]['trial_site']} "
                  f"({worst_site.iloc[0]['completion_rate']:.1f}% completion)")
        
        # Age trend analysis
        age_trend = analyzer.query_sqlite("""
            SELECT 
                ROUND(AVG(age), 2) as avg_age_all,
                (SELECT ROUND(AVG(age), 2) FROM patients WHERE completed_trial = 1) as avg_age_completed,
                (SELECT ROUND(AVG(age), 2) FROM patients WHERE completed_trial = 0) as avg_age_incomplete
            FROM patients
        """)
        
        if age_trend is not None:
            print(f"  Age Pattern: Patients who completed avg age {age_trend.iloc[0]['avg_age_completed']}, "
                  f"incomplete avg age {age_trend.iloc[0]['avg_age_incomplete']}")
        
        print("\n" + "="*70)
        print("ADVANCED ANALYSIS COMPLETE")
        print("="*70)
        
        print("\n" + "="*70)
        print("SQL QUERY DEMONSTRATIONS (Option E: Database Integration)")
        print("="*70)
        
        # Query 1: Detailed Patient Report
        print("\nQuery 1: Detailed Patient Report by Site")
        print("-" * 70)
        query1 = analyzer.query_sqlite("""
            SELECT 
                trial_site,
                COUNT(*) as total_patients,
                SUM(CASE WHEN completed_trial = 1 THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN completed_trial = 0 THEN 1 ELSE 0 END) as incomplete,
                SUM(CASE WHEN adverse_event = 1 THEN 1 ELSE 0 END) as with_adverse,
                SUM(CASE WHEN adverse_event = 0 THEN 1 ELSE 0 END) as without_adverse
            FROM patients
            GROUP BY trial_site
            ORDER BY trial_site
        """)
        
        if query1 is not None:
            print(f"{'Site':<15} {'Total':<8} {'Completed':<12} {'Incomplete':<12} "
                  f"{'With Adverse':<15} {'No Adverse':<12}")
            print("-" * 70)
            for idx, row in query1.iterrows():
                print(f"{row['trial_site']:<15} {row['total_patients']:<8} "
                      f"{row['completed']:<12} {row['incomplete']:<12} "
                      f"{row['with_adverse']:<15} {row['without_adverse']:<12}")
        
        # Query 2: Enrollment Timeline
        print("\nQuery 2: Enrollment Timeline (Chronological)")
        print("-" * 70)
        query2 = analyzer.query_sqlite("""
            SELECT 
                enrollment_date,
                COUNT(*) as enrollments,
                trial_site
            FROM patients
            GROUP BY enrollment_date, trial_site
            ORDER BY enrollment_date
            LIMIT 10
        """)
        
        if query2 is not None:
            print(f"{'Date':<15} {'Site':<15} {'Enrollments':<12}")
            print("-" * 70)
            for idx, row in query2.iterrows():
                print(f"{row['enrollment_date']:<15} {row['trial_site']:<15} {row['enrollments']:<12}")
        
        # Query 3: High-Risk Patients
        print("\nQuery 3: High-Risk Patients (Adverse Events + Incomplete)")
        print("-" * 70)
        query3 = analyzer.query_sqlite("""
            SELECT 
                patient_id,
                trial_site,
                age,
                adverse_event,
                completed_trial
            FROM patients
            WHERE adverse_event = 1 AND completed_trial = 0
            ORDER BY age DESC
        """)
        
        if query3 is not None:
            print(f"{'Patient ID':<12} {'Site':<15} {'Age':<6} {'Status':<20}")
            print("-" * 70)
            for idx, row in query3.iterrows():
                status = "Adverse + Incomplete"
                print(f"{row['patient_id']:<12} {row['trial_site']:<15} "
                      f"{int(row['age']):<6} {status:<20}")
            print(f"\nTotal high-risk patients: {len(query3)}")
        
        # Query 4: Site Completion Rates with Ranking
        print("\nQuery 4: Site Performance Ranking with Case Statements")
        print("-" * 70)
        query4 = analyzer.query_sqlite("""
            SELECT 
                trial_site,
                COUNT(*) as total,
                SUM(completed_trial) as completed,
                ROUND(100.0 * SUM(completed_trial) / COUNT(*), 2) as completion_pct,
                CASE 
                    WHEN ROUND(100.0 * SUM(completed_trial) / COUNT(*), 2) >= 90 THEN 'A (Excellent)'
                    WHEN ROUND(100.0 * SUM(completed_trial) / COUNT(*), 2) >= 70 THEN 'B (Good)'
                    WHEN ROUND(100.0 * SUM(completed_trial) / COUNT(*), 2) >= 50 THEN 'C (Fair)'
                    ELSE 'D (Poor)'
                END as grade
            FROM patients
            GROUP BY trial_site
            ORDER BY completion_pct DESC
        """)
        
        if query4 is not None:
            print(f"{'Site':<15} {'Total':<8} {'Completed':<12} {'Rate':<10} {'Grade':<15}")
            print("-" * 70)
            for idx, row in query4.iterrows():
                print(f"{row['trial_site']:<15} {row['total']:<8} "
                      f"{row['completed']:<12} {row['completion_pct']:<10.2f}% {row['grade']:<15}")
        
        # Query 5: Statistical Summary
        print("\nQuery 5: Statistical Summary of All Patients")
        print("-" * 70)
        query5 = analyzer.query_sqlite("""
            SELECT 
                COUNT(*) as total_patients,
                AVG(age) as avg_age,
                MIN(age) as youngest,
                MAX(age) as oldest,
                ROUND(100.0 * SUM(completed_trial) / COUNT(*), 2) as overall_completion_rate,
                ROUND(100.0 * SUM(adverse_event) / COUNT(*), 2) as overall_adverse_rate
            FROM patients
        """)
        
        if query5 is not None:
            row = query5.iloc[0]
            print(f"Total Patients: {int(row['total_patients'])}")
            print(f"Average Age: {row['avg_age']:.2f} years")
            print(f"Age Range: {int(row['youngest'])} - {int(row['oldest'])} years")
            print(f"Overall Completion Rate: {row['overall_completion_rate']:.2f}%")
            print(f"Overall Adverse Event Rate: {row['overall_adverse_rate']:.2f}%")
        
        print("\n" + "="*70)
        print("DATABASE QUERIES COMPLETE - All 5 SQL demonstrations executed successfully")
        print("="*70)
        
        # Visualizations
        charts = analyzer.create_visualizations()
        print(f"\n✓ {len(charts)} visualizations created")
        
    else:
        print("Failed to load data:")
        for error in analyzer.errors:
            print(f"  - {error}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'web':
        print("Starting Flask web server on http://localhost:5000")
        app.run(debug=True, port=5000)
    else:
        main()
