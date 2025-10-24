import pandas as pd
import numpy as np
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, Tuple


# Configure logging for validation only (file only, not console)
validation_logger = logging.getLogger('validation')
validation_logger.setLevel(logging.INFO)
validation_logger.propagate = False

# File handler for validation log
file_handler = logging.FileHandler('data_validation.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(levelname)-8s | %(message)s'))

validation_logger.addHandler(file_handler)

logger = validation_logger


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
            logger.info("")
            logger.info("="*70)
            logger.info(f"VALIDATION SESSION: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("="*70)
            logger.info(f"File: {self.csv_file}")
            
            # Read CSV with pandas (more efficient than csv module for validation)
            self.df = pd.read_csv(self.csv_file)
            logger.info(f"✓ Loaded {len(self.df)} records")
            
            # Validate required columns
            required_cols = ['patient_id', 'trial_site', 'enrollment_date', 
                           'age', 'adverse_event', 'completed_trial']
            missing_cols = [col for col in required_cols if col not in self.df.columns]
            if missing_cols:
                error_msg = f"Missing columns: {missing_cols}"
                self.errors.append(error_msg)
                logger.error(error_msg)
                return False
            
            # Data type conversions and validation
            original_len = len(self.df)
            
            # Convert and validate with detailed logging
            logger.info("Validating data types...")
            self.df['enrollment_date'] = pd.to_datetime(self.df['enrollment_date'], 
                                                         format='%Y-%m-%d', errors='coerce')
            date_invalid = self.df['enrollment_date'].isna().sum()
            if date_invalid > 0:
                logger.warning(f"  ⚠ {date_invalid} record(s) with invalid dates")
            
            self.df['age'] = pd.to_numeric(self.df['age'], errors='coerce')
            age_invalid = self.df['age'].isna().sum()
            if age_invalid > 0:
                logger.warning(f"  ⚠ {age_invalid} record(s) with invalid ages")
            
            self.df['adverse_event'] = self.df['adverse_event'].astype(str).str.lower().isin(['true', '1'])
            self.df['completed_trial'] = self.df['completed_trial'].astype(str).str.lower().isin(['true', '1'])
            
            # Flag invalid rows with detailed reasons
            invalid_mask = (
                self.df['enrollment_date'].isna() |
                self.df['age'].isna() |
                (self.df['age'] < 0) |
                (self.df['age'] > 150) |
                self.df['patient_id'].isna() |
                self.df['trial_site'].isna()
            )
            
            # Store invalid records with reasons
            self.invalid_records = []
            if invalid_mask.sum() > 0:
                logger.warning("")
                logger.warning("INVALID RECORDS FOUND:")
                logger.warning("-" * 70)
            
            for idx, row in self.df[invalid_mask].iterrows():
                reasons = []
                if pd.isna(row['enrollment_date']):
                    reasons.append("Invalid enrollment date")
                if pd.isna(row['age']) or row['age'] < 0 or row['age'] > 150:
                    reasons.append(f"Invalid age: {row['age']}")
                if pd.isna(row['patient_id']):
                    reasons.append("Missing patient ID")
                if pd.isna(row['trial_site']):
                    reasons.append("Missing trial site")
                
                invalid_record = row.to_dict()
                invalid_record['validation_errors'] = reasons
                self.invalid_records.append(invalid_record)
                
                # Log each invalid record cleanly
                logger.warning(f"  Patient {row.get('patient_id', 'UNKNOWN')}: {', '.join(reasons)}")
            
            if len(self.invalid_records) > 0:
                logger.warning("-" * 70)
                error_msg = f"Total: {len(self.invalid_records)} invalid record(s) excluded from analysis"
                self.errors.append(error_msg)
                logger.error(error_msg)
                print(f"\n⚠️  Found {len(self.invalid_records)} invalid records")
                print(f"📋 See 'data_validation.log' for details\n")
            
            # Keep only valid records
            self.df = self.df[~invalid_mask].reset_index(drop=True)
            logger.info("")
            logger.info(f"RESULT:")
            logger.info(f"  ✓ Valid: {len(self.df)} records")
            logger.info(f"  ✗ Invalid: {len(self.invalid_records)} records")
            logger.info("="*70)
            logger.info("")  # Blank line between sessions
            
            if len(self.df) == 0:
                error_msg = "No valid records found after validation"
                self.errors.append(error_msg)
                logger.error(error_msg)
                return False
            
            return True
            
        except Exception as e:
            error_msg = f"Error loading CSV: {str(e)}"
            self.errors.append(error_msg)
            logger.error(error_msg)
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
            'invalid_records': len(self.invalid_records),
            'invalid_record_details': self.invalid_records if self.invalid_records else []
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
        
        # Show detailed invalid record information
        if stats['data_quality']['invalid_records'] > 0:
            report.append("")
            report.append("INVALID RECORDS DETAILS")
            for i, invalid in enumerate(stats['data_quality']['invalid_record_details'][:5], 1):
                patient_id = invalid.get('patient_id', 'UNKNOWN')
                reasons = invalid.get('validation_errors', [])
                report.append(f"  {i}. Patient ID: {patient_id}")
                report.append(f"     Errors: {', '.join(reasons)}")
            if len(stats['data_quality']['invalid_record_details']) > 5:
                remaining = len(stats['data_quality']['invalid_record_details']) - 5
                report.append(f"  ... and {remaining} more (see data_validation.log)")
        
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
        
        # Convert pandas NaN/NaT/Timestamp to JSON-serializable types
        def clean_for_json(obj):
            if isinstance(obj, dict):
                return {k: clean_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_for_json(item) for item in obj]
            elif pd.isna(obj):
                return None
            elif isinstance(obj, (pd.Timestamp, datetime)):
                return obj.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(obj, (np.integer, np.floating)):
                return float(obj) if np.isfinite(obj) else None
            elif isinstance(obj, np.bool_):
                return bool(obj)
            else:
                return obj
        
        stats_clean = clean_for_json(stats)
        
        with open(output_file, 'w') as f:
            json.dump(stats_clean, f, indent=2)
        print(f"JSON exported to {output_file}")
    
    def load_to_sqlite(self):
        """Load data into SQLite database (Bonus E)."""
        try:
            conn = sqlite3.connect(self.db_path)
            self.df.to_sql('patients', conn, if_exists='replace', index=False)
            conn.close()
            print(f"Data loaded to SQLite: {self.db_path}")
        except Exception as e:
            error_msg = f"SQLite error: {str(e)}"
            self.errors.append(error_msg)
            logger.error(error_msg)
    
    def query_sqlite(self, query: str):
        """Query SQLite database."""
        try:
            conn = sqlite3.connect(self.db_path)
            result = pd.read_sql_query(query, conn)
            conn.close()
            return result
        except Exception as e:
            error_msg = f"Query error: {str(e)}"
            self.errors.append(error_msg)
            logger.error(error_msg)
            return None
    
    def get_advanced_analysis(self) -> Dict:
        """Advanced analysis: trends and patterns (Bonus D)."""
        if self.df is None or len(self.df) == 0:
            return {}
        
        # Site performance analysis
        site_analysis = self.df.groupby('trial_site').agg({
            'completed_trial': ['sum', 'count', 'mean'],
            'adverse_event': 'sum',
            'age': 'mean'
        }).round(2)
        
        # Age group analysis
        self.df['age_group'] = pd.cut(self.df['age'], 
                                       bins=[0, 35, 50, 65, 150],
                                       labels=['18-35', '36-50', '51-65', '65+'])
        age_group_analysis = self.df.groupby('age_group').agg({
            'completed_trial': ['sum', 'count', 'mean']
        }).round(2)
        
        # Correlation analysis
        numeric_cols = ['age', 'adverse_event', 'completed_trial']
        correlations = self.df[numeric_cols].corr().round(3)
        
        return {
            'site_performance': site_analysis.to_dict(),
            'age_group_analysis': age_group_analysis.to_dict(),
            'correlations': correlations.to_dict()
        }
    
    def create_visualizations(self) -> Dict[str, go.Figure]:
        """Create all visualizations (Bonus C) with improved styling."""
        if self.df is None or len(self.df) == 0:
            return {}
        
        charts = {}
        
        # Chart 1: Enrollment Over Time
        enrollment_by_date = self.df.groupby('enrollment_date').size().reset_index(name='count')
        fig1 = px.line(enrollment_by_date, 
                      x='enrollment_date', 
                      y='count',
                      title='Patient Enrollment Timeline',
                      labels={'enrollment_date': 'Enrollment Date', 
                             'count': 'Number of Patients'},
                      markers=True)
        fig1.update_traces(line_color='#2E86AB', line_width=3, marker=dict(size=8))
        fig1.update_layout(
            hovermode='x unified',
            plot_bgcolor='white',
            yaxis=dict(title='Number of Patients', gridcolor='lightgray')
        )
        charts['enrollment_timeline'] = fig1
        
        # Chart 2: Site Comparison (Side-by-Side Bars)
        site_completion = self.df.groupby(['trial_site', 'completed_trial']).size().reset_index(name='count')
        site_completion['status'] = site_completion['completed_trial'].map({
            True: 'Completed Trial', 
            False: 'Did Not Complete Trial'
        })
        
        fig2 = px.bar(site_completion, 
                     x='trial_site', 
                     y='count',
                     color='status',
                     title='Trial Completion Status by Site (Side-by-Side Comparison)',
                     labels={'trial_site': 'Trial Site', 
                            'count': 'Number of Patients',
                            'status': 'Trial Status'},
                     barmode='group',  # Side-by-side bars
                     color_discrete_map={
                         'Completed Trial': '#06A77D',
                         'Did Not Complete Trial': '#D62246'
                     })
        fig2.update_layout(
            plot_bgcolor='white',
            yaxis=dict(title='Number of Patients', gridcolor='lightgray'),
            legend=dict(title='Trial Status', orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        charts['site_completion'] = fig2
        
        # Chart 3: Age Distribution with lines between bars and values on bars
        age_bins = [0, 35, 45, 55, 65, 150]
        age_labels = ['18-35', '36-45', '46-55', '56-65', '65+']
        self.df['age_group'] = pd.cut(self.df['age'], bins=age_bins, labels=age_labels)
        age_dist = self.df['age_group'].value_counts().sort_index().reset_index()
        age_dist.columns = ['age_group', 'count']
        
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            x=age_dist['age_group'],
            y=age_dist['count'],
            marker_color='#F18F01',
            marker_line_color='#333333',  # Lines between bars
            marker_line_width=2,
            text=age_dist['count'],  # Values on bars
            textposition='outside',
            textfont=dict(size=12, color='black'),
            name='Patient Count',
            hovertemplate='<b>Age Group:</b> %{x}<br>' +
                         '<b>Number of Patients:</b> %{y}<br>' +
                         '<extra></extra>'
        ))
        fig3.update_layout(
            title='Patient Age Distribution (with counts displayed)',
            xaxis=dict(title='Age Group (Years)'),
            yaxis=dict(title='Number of Patients', gridcolor='lightgray'),
            plot_bgcolor='white',
            showlegend=False
        )
        charts['age_distribution'] = fig3
        
        # Chart 4: Adverse Events Pie Chart
        adverse_counts = self.df['adverse_event'].value_counts()
        labels = ['No Adverse Events', 'Experienced Adverse Events']
        values = [adverse_counts.get(False, 0), adverse_counts.get(True, 0)]
        
        fig4 = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker_colors=['#06A77D', '#D62246'],
            textinfo='percent',
            textfont_size=16,
            textposition='inside',
            insidetextorientation='horizontal',
            hovertemplate='<b>%{label}</b><br>' +
                         'Patients: %{value}<br>' +
                         'Percentage: %{percent}<br>' +
                         '<extra></extra>'
        )])
        fig4.update_layout(
            title='Adverse Event Distribution Across All Patients',
            showlegend=True,
            legend=dict(title='Event Status', orientation='v', yanchor='top', y=1, xanchor='left', x=0)
        )
        charts['adverse_events'] = fig4
        
        return charts


# Flask Web Application (Bonus A)
app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Clinical Trial Data Analyzer</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #2E86AB 0%, #06A77D 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
        }
        .upload-section {
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 5px solid #2E86AB;
        }
        .stat-card h3 {
            margin: 0 0 10px 0;
            color: #333;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .stat-card .value {
            font-size: 2.5em;
            font-weight: bold;
            color: #2E86AB;
            margin: 0;
        }
        .chart-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .site-breakdown {
            background: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .site-breakdown h2 {
            margin-top: 0;
            color: #333;
        }
        .site-item {
            display: flex;
            justify-content: space-between;
            padding: 15px;
            border-bottom: 1px solid #eee;
            align-items: center;
        }
        .site-item:last-child {
            border-bottom: none;
        }
        .site-name {
            font-weight: bold;
            color: #2E86AB;
            font-size: 1.1em;
        }
        .site-count {
            background: #2E86AB;
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            font-weight: bold;
        }
        button {
            background: #06A77D;
            color: white;
            border: none;
            padding: 12px 30px;
            font-size: 1em;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s;
        }
        button:hover {
            background: #048a66;
        }
        input[type="file"] {
            padding: 10px;
            border: 2px dashed #2E86AB;
            border-radius: 5px;
            width: 100%;
            margin-bottom: 15px;
        }
        .alert {
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .alert-warning {
            background-color: #fff3cd;
            border: 1px solid #ffc107;
            color: #856404;
        }
        .alert-error {
            background-color: #f8d7da;
            border: 1px solid #dc3545;
            color: #721c24;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Clinical Trial Data Analyzer</h1>
        <p>Advanced Analytics Dashboard with Interactive Visualizations</p>
    </div>

    <div class="upload-section">
        <h2>Upload Trial Data</h2>
        <form method="POST" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Analyze Data</button>
        </form>
    </div>

    {% if stats %}
    {% if stats.data_quality.invalid_records > 0 %}
    <div class="alert alert-warning">
        <strong>⚠️ Data Quality Notice:</strong> Found {{ stats.data_quality.invalid_records }} invalid record(s). 
        These have been excluded from analysis. Check 'data_validation.log' and 'trial_results.json' for details.
    </div>
    {% endif %}

    <div class="stats-grid">
        <div class="stat-card">
            <h3>Total Patients</h3>
            <p class="value">{{ stats.total_patients }}</p>
        </div>
        <div class="stat-card">
            <h3>Average Age</h3>
            <p class="value">{{ stats.average_age }}</p>
        </div>
        <div class="stat-card">
            <h3>Completion Rate</h3>
            <p class="value">{{ stats.completion_rate_percent }}%</p>
        </div>
        <div class="stat-card">
            <h3>Adverse Event Rate</h3>
            <p class="value">{{ stats.adverse_event_rate_percent }}%</p>
        </div>
    </div>

    <div class="site-breakdown">
        <h2>🎯 Completion by Adverse Event Status</h2>
        <div class="site-item">
            <span class="site-name">With Adverse Events</span>
            <span class="site-count">{{ stats.completion_rate_with_adverse_percent }}%</span>
        </div>
        <div class="site-item">
            <span class="site-name">Without Adverse Events</span>
            <span class="site-count">{{ stats.completion_rate_without_adverse_percent }}%</span>
        </div>
        <p style="margin-top: 15px; color: #666; font-style: italic;">
            Patients without adverse events are {{ (stats.completion_rate_without_adverse_percent - stats.completion_rate_with_adverse_percent)|round(1) }}% 
            more likely to complete the trial.
        </p>
    </div>

    <div class="site-breakdown">
        <h2>📍 Patients Per Trial Site</h2>
        {% for site, count in stats.patients_per_site.items() %}
        <div class="site-item">
            <span class="site-name">{{ site }}</span>
            <span class="site-count">{{ count }} patients</span>
        </div>
        {% endfor %}
    </div>

    {% for chart_name, chart_html in charts.items() %}
    <div class="chart-container">
        {{ chart_html|safe }}
    </div>
    {% endfor %}

    <div class="site-breakdown">
        <h2>💾 Database Query Results (SQL Demonstrations)</h2>
        
        <h3 style="margin-top: 25px; color: #2E86AB;">Query 1: Patient Report by Site</h3>
        <p style="color: #666; margin-bottom: 10px;">
            <strong>Purpose:</strong> This query provides a comprehensive breakdown of patient outcomes at each trial site, 
            showing total patients, completion status, and adverse event counts. It helps identify which sites are performing 
            well and which may need additional support.
        </p>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <thead>
                    <tr style="background-color: #2E86AB; color: white;">
                        <th style="padding: 12px; text-align: left;">Site</th>
                        <th style="padding: 12px; text-align: left;">Total</th>
                        <th style="padding: 12px; text-align: left;">Completed</th>
                        <th style="padding: 12px; text-align: left;">Incomplete</th>
                        <th style="padding: 12px; text-align: left;">With Adverse</th>
                        <th style="padding: 12px; text-align: left;">No Adverse</th>
                    </tr>
                </thead>
                <tbody>
                    {% for site, data in sql_query1.items() %}
                    <tr style="border-bottom: 1px solid #ddd;">
                        <td style="padding: 12px;">{{ site }}</td>
                        <td style="padding: 12px;">{{ data.total }}</td>
                        <td style="padding: 12px; color: #06A77D; font-weight: bold;">{{ data.completed }}</td>
                        <td style="padding: 12px; color: #D62246;">{{ data.incomplete }}</td>
                        <td style="padding: 12px;">{{ data.with_adverse }}</td>
                        <td style="padding: 12px;">{{ data.without_adverse }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <h3 style="margin-top: 25px; color: #2E86AB;">Query 2: Enrollment Summary by Site</h3>
        <p style="color: #666; margin-bottom: 10px;">
            <strong>Purpose:</strong> This query compares total patient enrollment across different trial sites and shows 
            the enrollment timeline for each site. It helps identify enrollment patterns and whether sites are enrolling 
            patients at similar rates.
        </p>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <thead>
                    <tr style="background-color: #2E86AB; color: white;">
                        <th style="padding: 12px; text-align: left;">Site</th>
                        <th style="padding: 12px; text-align: left;">Total Enrolled</th>
                        <th style="padding: 12px; text-align: left;">First Patient</th>
                        <th style="padding: 12px; text-align: left;">Last Patient</th>
                    </tr>
                </thead>
                <tbody>
                    {% for site, data in sql_query2.items() %}
                    <tr style="border-bottom: 1px solid #ddd;">
                        <td style="padding: 12px;">{{ site }}</td>
                        <td style="padding: 12px; font-weight: bold;">{{ data.total }}</td>
                        <td style="padding: 12px;">{{ data.first }}</td>
                        <td style="padding: 12px;">{{ data.last }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <h3 style="margin-top: 25px; color: #2E86AB;">Query 3: High-Risk Patients</h3>
        <p style="color: #666; margin-bottom: 10px;">
            <strong>Purpose:</strong> This query identifies patients who both experienced adverse events AND did not complete 
            the trial. These patients represent high-risk cases that may require follow-up or indicate potential safety concerns. 
            The list is ordered by age to help identify if certain age groups are more vulnerable.
        </p>
        <p style="color: #D62246; font-weight: bold; margin-bottom: 10px;">
            Total High-Risk Patients: {{ sql_query3_count }}
        </p>
        {% if sql_query3_list|length > 0 %}
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <thead>
                    <tr style="background-color: #D62246; color: white;">
                        <th style="padding: 12px; text-align: left;">Patient ID</th>
                        <th style="padding: 12px; text-align: left;">Site</th>
                        <th style="padding: 12px; text-align: left;">Age</th>
                        <th style="padding: 12px; text-align: left;">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for patient in sql_query3_list %}
                    <tr style="border-bottom: 1px solid #ddd; background-color: #fff5f5;">
                        <td style="padding: 12px; font-weight: bold;">{{ patient.id }}</td>
                        <td style="padding: 12px;">{{ patient.site }}</td>
                        <td style="padding: 12px;">{{ patient.age }}</td>
                        <td style="padding: 12px; color: #D62246;">{{ patient.status }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}

        <h3 style="margin-top: 25px; color: #2E86AB;">Query 4: Site Performance Rankings</h3>
        <p style="color: #666; margin-bottom: 10px;">
            <strong>Purpose:</strong> This query uses SQL CASE statements to automatically grade each site's performance 
            based on completion rates. Sites with 90%+ completion get an "A", 70-89% get "B", 50-69% get "C", and below 50% 
            get "D". This makes it easy to quickly assess which sites are meeting quality standards.
        </p>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <thead>
                    <tr style="background-color: #2E86AB; color: white;">
                        <th style="padding: 12px; text-align: left;">Site</th>
                        <th style="padding: 12px; text-align: left;">Total</th>
                        <th style="padding: 12px; text-align: left;">Completed</th>
                        <th style="padding: 12px; text-align: left;">Completion %</th>
                        <th style="padding: 12px; text-align: left;">Grade</th>
                    </tr>
                </thead>
                <tbody>
                    {% for site, data in sql_query4.items() %}
                    <tr style="border-bottom: 1px solid #ddd;">
                        <td style="padding: 12px;">{{ site }}</td>
                        <td style="padding: 12px;">{{ data.total }}</td>
                        <td style="padding: 12px;">{{ data.completed }}</td>
                        <td style="padding: 12px; font-weight: bold;">{{ data.rate }}%</td>
                        <td style="padding: 12px; 
                            {% if 'Excellent' in data.grade %}color: #06A77D; font-weight: bold;
                            {% elif 'Good' in data.grade %}color: #F18F01; font-weight: bold;
                            {% else %}color: #D62246; font-weight: bold;{% endif %}">
                            {{ data.grade }}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <h3 style="margin-top: 25px; color: #2E86AB;">Query 5: Overall Statistical Summary</h3>
        <p style="color: #666; margin-bottom: 10px;">
            <strong>Purpose:</strong> This query calculates aggregate statistics across the entire dataset using SQL 
            aggregate functions (COUNT, AVG, MIN, MAX). It provides a bird's-eye view of the trial's overall performance 
            and patient demographics in a single summary.
        </p>
        <div style="background: #f9f9f9; padding: 20px; border-radius: 8px; border-left: 4px solid #2E86AB;">
            <p><strong>Total Patients:</strong> {{ sql_query5.total }}</p>
            <p><strong>Average Age:</strong> {{ sql_query5.avg_age }} years</p>
            <p><strong>Age Range:</strong> {{ sql_query5.min_age }} - {{ sql_query5.max_age }} years</p>
            <p><strong>Overall Completion Rate:</strong> {{ sql_query5.completion_rate }}%</p>
            <p><strong>Overall Adverse Event Rate:</strong> {{ sql_query5.adverse_rate }}%</p>
        </div>
    </div>
    {% endif %}
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main web interface route."""
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename.endswith('.csv'):
            # Save uploaded file temporarily
            temp_path = 'temp_upload.csv'
            file.save(temp_path)
            
            # Analyze data
            analyzer = TrialDataAnalyzer(temp_path)
            if analyzer.load_and_validate_data():
                stats = analyzer.calculate_statistics()
                charts_dict = analyzer.create_visualizations()
                
                # Convert charts to HTML
                charts_html = {}
                for name, fig in charts_dict.items():
                    charts_html[name] = fig.to_html(full_html=False, include_plotlyjs=False)
                
                # Export results
                analyzer.export_to_json()
                analyzer.load_to_sqlite()
                
                # Execute SQL queries for web display
                query1_result = analyzer.query_sqlite("""
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
                
                query2_result = analyzer.query_sqlite("""
                    SELECT 
                        trial_site,
                        COUNT(*) as total_enrolled,
                        MIN(enrollment_date) as first_enrollment,
                        MAX(enrollment_date) as last_enrollment
                    FROM patients
                    GROUP BY trial_site
                    ORDER BY total_enrolled DESC
                """)
                
                query3_result = analyzer.query_sqlite("""
                    SELECT 
                        patient_id,
                        trial_site,
                        age
                    FROM patients
                    WHERE adverse_event = 1 AND completed_trial = 0
                    ORDER BY age DESC
                """)
                
                query3_count_result = analyzer.query_sqlite("""
                    SELECT COUNT(*) as high_risk_count
                    FROM patients
                    WHERE adverse_event = 1 AND completed_trial = 0
                """)
                
                query4_result = analyzer.query_sqlite("""
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
                
                query5_result = analyzer.query_sqlite("""
                    SELECT 
                        COUNT(*) as total_patients,
                        ROUND(AVG(age), 2) as avg_age,
                        MIN(age) as youngest,
                        MAX(age) as oldest,
                        ROUND(100.0 * SUM(completed_trial) / COUNT(*), 2) as overall_completion_rate,
                        ROUND(100.0 * SUM(adverse_event) / COUNT(*), 2) as overall_adverse_rate
                    FROM patients
                """)
                
                # Format query results for template
                sql_query1 = {}
                if query1_result is not None:
                    for _, row in query1_result.iterrows():
                        sql_query1[row['trial_site']] = {
                            'total': int(row['total_patients']),
                            'completed': int(row['completed']),
                            'incomplete': int(row['incomplete']),
                            'with_adverse': int(row['with_adverse']),
                            'without_adverse': int(row['without_adverse'])
                        }
                
                sql_query2 = {}
                if query2_result is not None:
                    for _, row in query2_result.iterrows():
                        sql_query2[row['trial_site']] = {
                            'total': int(row['total_enrolled']),
                            'first': str(row['first_enrollment'])[:10],
                            'last': str(row['last_enrollment'])[:10]
                        }
                
                sql_query3_count = 0
                sql_query3_list = []
                if query3_count_result is not None:
                    sql_query3_count = int(query3_count_result.iloc[0]['high_risk_count'])
                
                if query3_result is not None:
                    for _, row in query3_result.iterrows():
                        sql_query3_list.append({
                            'id': row['patient_id'],
                            'site': row['trial_site'],
                            'age': int(row['age']),
                            'status': 'Adverse + Incomplete'
                        })
                
                sql_query4 = {}
                if query4_result is not None:
                    for _, row in query4_result.iterrows():
                        sql_query4[row['trial_site']] = {
                            'total': int(row['total']),
                            'completed': int(row['completed']),
                            'rate': float(row['completion_pct']),
                            'grade': row['grade']
                        }
                
                sql_query5 = {}
                if query5_result is not None:
                    row = query5_result.iloc[0]
                    sql_query5 = {
                        'total': int(row['total_patients']),
                        'avg_age': float(row['avg_age']),
                        'min_age': int(row['youngest']),
                        'max_age': int(row['oldest']),
                        'completion_rate': float(row['overall_completion_rate']),
                        'adverse_rate': float(row['overall_adverse_rate'])
                    }
                
                return render_template_string(HTML_TEMPLATE, 
                                            stats=stats, 
                                            charts=charts_html,
                                            sql_query1=sql_query1,
                                            sql_query2=sql_query2,
                                            sql_query3_count=sql_query3_count,
                                            sql_query3_list=sql_query3_list,
                                            sql_query4=sql_query4,
                                            sql_query5=sql_query5)
            else:
                error_msg = '<br>'.join(analyzer.errors)
                return f'<div class="alert alert-error">Error: {error_msg}</div>'
    
    return render_template_string(HTML_TEMPLATE, stats=None, charts=None)


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """REST API endpoint for data analysis (Bonus B)."""
    file = request.files.get('file')
    if not file or not file.filename.endswith('.csv'):
        return jsonify({'error': 'Valid CSV file required'}), 400
    
    temp_path = 'temp_upload.csv'
    file.save(temp_path)
    
    analyzer = TrialDataAnalyzer(temp_path)
    if analyzer.load_and_validate_data():
        stats = analyzer.calculate_statistics()
        return jsonify(stats), 200
    else:
        return jsonify({'errors': analyzer.errors}), 400


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'Clinical Trial Analyzer'}), 200


def main():
    """Main execution function for console mode."""
    csv_file = "trial_data.csv"
    
    if not Path(csv_file).exists():
        print(f"Error: {csv_file} not found")
        logger.error(f"CSV file not found: {csv_file}")
        return
    
    print("="*70)
    print("CLINICAL TRIAL DATA ANALYZER")
    print("="*70)
    print()
    
    analyzer = TrialDataAnalyzer(csv_file)
    
    if analyzer.load_and_validate_data():
        # Generate and display report
        report = analyzer.generate_text_report()
        print(report)
        
        # Export results
        analyzer.export_to_json()
        analyzer.load_to_sqlite()
        
        # Advanced analysis
        print("\n" + "="*70)
        print("ADVANCED ANALYSIS (Option D: Advanced Insights)")
        print("="*70)
        
        advanced = analyzer.get_advanced_analysis()
        
        # Site Performance
        print("\nSite Performance Analysis:")
        print("-" * 70)
        site_stats = analyzer.df.groupby('trial_site').agg({
            'completed_trial': ['sum', lambda x: f"{(x.sum()/len(x)*100):.1f}%"],
            'adverse_event': 'sum',
            'age': lambda x: f"{x.mean():.1f}"
        }).round(2)
        
        print(f"{'Site':<15} {'Completed':<12} {'Rate':<12} {'Adverse':<12} {'Avg Age':<10}")
        print("-" * 70)
        for site in site_stats.index:
            completed = int(analyzer.df[analyzer.df['trial_site']==site]['completed_trial'].sum())
            total = len(analyzer.df[analyzer.df['trial_site']==site])
            rate = (completed/total*100)
            adverse = int(analyzer.df[analyzer.df['trial_site']==site]['adverse_event'].sum())
            avg_age = analyzer.df[analyzer.df['trial_site']==site]['age'].mean()
            print(f"{site:<15} {completed:<12} {rate:<11.1f}% {adverse:<12} {avg_age:<10.1f}")
        
        # Correlation insights
        print("\nKey Correlations:")
        print("-" * 70)
        corr_matrix = analyzer.df[['age', 'adverse_event', 'completed_trial']].corr()
        age_adverse_corr = corr_matrix.loc['age', 'adverse_event']
        age_complete_corr = corr_matrix.loc['age', 'completed_trial']
        adverse_complete_corr = corr_matrix.loc['adverse_event', 'completed_trial']
        
        print(f"  Age vs Adverse Events: {age_adverse_corr:.3f} "
              f"({'Positive' if age_adverse_corr > 0 else 'Negative'} correlation)")
        print(f"  Age vs Completion: {age_complete_corr:.3f} "
              f"({'Positive' if age_complete_corr > 0 else 'Negative'} correlation)")
        print(f"  Adverse Events vs Completion: {adverse_complete_corr:.3f} "
              f"({'Positive' if adverse_complete_corr > 0 else 'Negative'} correlation)")
        
        # Adverse event impact
        print("\nAdverse Event Impact on Trial Completion:")
        print("-" * 70)
        adverse_impact = analyzer.df.groupby('adverse_event').agg({
            'completed_trial': lambda x: (x.sum()/len(x)*100)
        }).round(1)
        adverse_impact.columns = ['completion_rate']
        
        if len(adverse_impact) == 2:
            with_adverse = adverse_impact[adverse_impact.index == 1]['completion_rate'].values
            without_adverse = adverse_impact[adverse_impact.index == 0]['completion_rate'].values
            
            if len(with_adverse) > 0 and len(without_adverse) > 0:
                impact_difference = without_adverse[0] - with_adverse[0]
                print(f"  Patients WITHOUT adverse events are {impact_difference:.1f}% "
                      f"more likely to complete the trial")
        
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
        
        # Query 2: Enrollment Summary by Site and Month
        print("\nQuery 2: Patient Enrollment Summary by Site")
        print("-" * 70)
        query2 = analyzer.query_sqlite("""
            SELECT 
                trial_site,
                COUNT(*) as total_enrolled,
                MIN(enrollment_date) as first_enrollment,
                MAX(enrollment_date) as last_enrollment
            FROM patients
            GROUP BY trial_site
            ORDER BY total_enrolled DESC
        """)
        
        if query2 is not None:
            print(f"{'Site':<15} {'Total Enrolled':<15} {'First Patient':<20} {'Last Patient':<20}")
            print("-" * 70)
            for idx, row in query2.iterrows():
                print(f"{row['trial_site']:<15} {row['total_enrolled']:<15} "
                      f"{row['first_enrollment']:<20} {row['last_enrollment']:<20}")
            print(f"\nThis shows enrollment distribution and timeline across sites.")
        
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
        app.run(debug=True, port=5000)
    else:
        main()
