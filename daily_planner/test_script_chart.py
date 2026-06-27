"""
Generate two PDFs side-by-side for comparison:
1. Without trend charts
2. With trend charts

This helps verify if charts are actually being added.
"""

import os
from pathlib import Path
from datetime import datetime

# Find database
def find_database():
    possible_paths = [
        "prod_db.db",
        Path.home() / "OneDrive - whitebird.ca" / "Paper App" / "prod_db.db",
        Path.home() / "OneDrive" / "Paper App" / "prod_db.db",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return str(path)
    return None

db_path = find_database()
if not db_path:
    print("❌ Database not found!")
    exit(1)

print("=" * 70)
print("PDF COMPARISON TEST")
print("=" * 70)
print(f"Database: {db_path}")
print(f"Date: {datetime.today().strftime('%Y-%m-%d')}")
print()

try:
    from daily_planner_report import DailyPlannerReport
except ImportError as e:
    print(f"❌ Cannot import DailyPlannerReport: {e}")
    exit(1)

today = datetime.today().strftime("%Y-%m-%d")
output_dir = "./comparison_test"
os.makedirs(output_dir, exist_ok=True)

results = {}

# Test 1: Generate WITHOUT trend charts
print("\n" + "=" * 70)
print("TEST 1: Generating PDF WITHOUT Trend Charts")
print("=" * 70)

try:
    planner = DailyPlannerReport(
        db_path=db_path,
        planned_date=today,
        output_dir=output_dir,
        include_trend_charts=False  # NO CHARTS
    )
    
    pdf_path = planner.generate()
    
    if pdf_path and os.path.exists(pdf_path):
        file_size = os.path.getsize(pdf_path)
        results['without_charts'] = {
            'path': pdf_path,
            'size': file_size,
            'chart_count': len(planner.chart_figs)
        }
        print(f"✅ Generated: {os.path.basename(pdf_path)}")
        print(f"   File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        print(f"   Charts in object: {len(planner.chart_figs)}")
    else:
        print("❌ Failed to generate PDF without charts")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Generate WITH trend charts
print("\n" + "=" * 70)
print("TEST 2: Generating PDF WITH Trend Charts")
print("=" * 70)

try:
    planner = DailyPlannerReport(
        db_path=db_path,
        planned_date=today,
        output_dir=output_dir,
        include_trend_charts=True  # WITH CHARTS
    )
    
    print(f"Initial chart_figs count: {len(planner.chart_figs)}")
    
    pdf_path = planner.generate()
    
    print(f"Final chart_figs count: {len(planner.chart_figs)}")
    
    if pdf_path and os.path.exists(pdf_path):
        file_size = os.path.getsize(pdf_path)
        results['with_charts'] = {
            'path': pdf_path,
            'size': file_size,
            'chart_count': len(planner.chart_figs)
        }
        print(f"✅ Generated: {os.path.basename(pdf_path)}")
        print(f"   File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        print(f"   Charts in object: {len(planner.chart_figs)}")
    else:
        print("❌ Failed to generate PDF with charts")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Analysis
print("\n" + "=" * 70)
print("COMPARISON RESULTS")
print("=" * 70)

if 'without_charts' in results and 'with_charts' in results:
    without = results['without_charts']
    with_charts = results['with_charts']
    
    size_diff = with_charts['size'] - without['size']
    size_diff_kb = size_diff / 1024
    
    print(f"\n📊 File Size Comparison:")
    print(f"   WITHOUT charts: {without['size']:>10,} bytes ({without['size']/1024:>6.1f} KB)")
    print(f"   WITH charts:    {with_charts['size']:>10,} bytes ({with_charts['size']/1024:>6.1f} KB)")
    print(f"   Difference:     {size_diff:>10,} bytes ({size_diff_kb:>6.1f} KB)")
    
    print(f"\n📈 Chart Count:")
    print(f"   WITHOUT charts: {without['chart_count']} charts")
    print(f"   WITH charts:    {with_charts['chart_count']} charts")
    
    print(f"\n📁 Files Generated:")
    print(f"   WITHOUT: {without['path']}")
    print(f"   WITH:    {with_charts['path']}")
    
    print(f"\n" + "=" * 70)
    print("DIAGNOSIS")
    print("=" * 70)
    
    if size_diff < 10000:  # Less than 10 KB difference
        print("❌ PROBLEM DETECTED!")
        print("   The file sizes are nearly identical (< 10 KB difference)")
        print("   This means charts are NOT being added to the PDF")
        print()
        print("   Possible causes:")
        print("   1. chart_figs list is empty when building PDF")
        print("   2. _add_charts_to_elements() is not being called")
        print("   3. Charts are failing to convert to images")
        print("   4. Charts are being added but then removed/cleared")
        
    elif with_charts['chart_count'] == 0:
        print("❌ PROBLEM DETECTED!")
        print("   No charts in chart_figs list")
        print("   _generate_trend_charts() is not working")
        
    else:
        print("✅ CHARTS ARE BEING ADDED!")
        print(f"   File size increased by {size_diff_kb:.1f} KB")
        print(f"   {with_charts['chart_count']} charts in memory")
        print()
        print("   Open the PDF to verify charts are visible:")
        print(f"   {with_charts['path']}")
        
        # Try to open it
        import webbrowser
        try:
            webbrowser.open(with_charts['path'])
            print("\n✅ PDF opened in default viewer")
        except:
            pass

else:
    print("❌ Could not generate both PDFs for comparison")

# Log file analysis
print("\n" + "=" * 70)
print("LOG FILE ANALYSIS")
print("=" * 70)

log_file = "daily_planner_gui.log"
if os.path.exists(log_file):
    print(f"Reading last 30 lines from: {log_file}\n")
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            relevant_lines = [l for l in lines if any(keyword in l for keyword in [
                'TREND CHART',
                'chart_figs',
                'Chart count',
                'Adding',
                'Added chart'
            ])]
            
            if relevant_lines:
                print("Relevant log entries:")
                print("-" * 70)
                for line in relevant_lines[-30:]:
                    print(line.rstrip())
            else:
                print("⚠️  No chart-related log entries found")
                print("Last 10 lines of log:")
                print("-" * 70)
                for line in lines[-10:]:
                    print(line.rstrip())
    except Exception as e:
        print(f"Error reading log: {e}")
else:
    print(f"⚠️  Log file not found: {log_file}")

print("\n" + "=" * 70)