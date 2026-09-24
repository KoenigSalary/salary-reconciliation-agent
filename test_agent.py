"""
Manual Test Script
Use this to test the agent manually without waiting for scheduled dates
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from main import SalaryReconciliationAgent
from config import Config

def print_header(text):
    print("\n" + "=" * 80)
    print(text.center(80))
    print("=" * 80 + "\n")

def test_configuration():
    """Test if configuration is properly set"""
    print_header("TESTING CONFIGURATION")
    
    required_vars = [
        'RMS_USERNAME', 'RMS_PASSWORD', 
        'SENDER_EMAIL', 'SENDER_PASSWORD',
        'RECIPIENT_EMAILS'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
            print(f"❌ {var}: NOT SET")
        else:
            # Mask passwords
            if 'PASSWORD' in var:
                display_value = '*' * len(value)
            elif 'EMAIL' in var:
                display_value = value
            else:
                display_value = value[:10] + '...' if len(value) > 10 else value
            print(f"✓ {var}: {display_value}")
    
    if missing_vars:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please configure .env file before running")
        return False
    else:
        print("\n✅ All configuration variables are set")
        return True

def test_directories():
    """Test if required directories exist"""
    print_header("TESTING DIRECTORIES")
    
    directories = [
        Config.DOWNLOAD_DIR,
        Config.EPF_UPLOAD_DIR,
        Config.REPORTS_DIR,
        Config.LOGS_DIR
    ]
    
    all_exist = True
    for directory in directories:
        if Path(directory).exists():
            print(f"✓ {directory}")
        else:
            print(f"❌ {directory} - Creating...")
            Path(directory).mkdir(parents=True, exist_ok=True)
            all_exist = False
    
    if all_exist:
        print("\n✅ All directories exist")
    else:
        print("\n✅ Missing directories created")
    
    return True

def test_date_logic():
    """Test date calculation logic"""
    print_header("TESTING DATE LOGIC")
    
    target_months = Config.get_target_months()
    
    print(f"Current Date: {datetime.now().strftime('%d %B %Y')}")
    print(f"Current Day: {datetime.now().day}")
    print()
    print("Calculated Target Months:")
    print(f"  Salary Month: {target_months['salary_month_str']}")
    print(f"  TDS Month: {target_months['salary_month_str']}")
    print(f"  EPF Month: {target_months['salary_month_str']}")
    print(f"  Bank SOA Month: {target_months['bank_month_str']}")
    print()
    print("Date Ranges:")
    print(f"  Bank Start Date: {target_months['bank_start_date']}")
    print(f"  Bank End Date: {target_months['bank_end_date']}")
    
    print("\n✅ Date logic working correctly")
    return True

def test_epf_reminder():
    """Test sending EPF reminder email"""
    print_header("TESTING EPF REMINDER EMAIL")
    
    response = input("Do you want to send a test EPF reminder email? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        agent = SalaryReconciliationAgent()
        success = agent.send_epf_reminder()
        
        if success:
            print("\n✅ EPF reminder email sent successfully")
        else:
            print("\n❌ Failed to send EPF reminder email")
        
        return success
    else:
        print("Skipped EPF reminder test")
        return True

def test_full_reconciliation():
    """Test full reconciliation process"""
    print_header("TESTING FULL RECONCILIATION")
    
    print("⚠️  This will:")
    print("  1. Login to RMS portal")
    print("  2. Download Salary Sheet, TDS Sheet, and Bank SOA")
    print("  3. Look for EPF file in uploads directory")
    print("  4. Perform reconciliation")
    print("  5. Generate reports")
    print("  6. Send email with results")
    print()
    
    # Check if EPF file exists
    epf_files = list(Path(Config.EPF_UPLOAD_DIR).glob("*.xlsx")) + \
                list(Path(Config.EPF_UPLOAD_DIR).glob("*.xls"))
    
    if not epf_files:
        print(f"⚠️  WARNING: No EPF file found in {Config.EPF_UPLOAD_DIR}")
        print("Please upload an EPF file before running reconciliation")
        response = input("Continue anyway? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Skipped full reconciliation test")
            return True
    else:
        print(f"✓ Found EPF file: {epf_files[0].name}")
    
    print()
    response = input("Proceed with full reconciliation? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        agent = SalaryReconciliationAgent()
        success = agent.run_full_reconciliation()
        
        if success:
            print("\n✅ Full reconciliation completed successfully")
        else:
            print("\n❌ Full reconciliation failed (check logs for details)")
        
        return success
    else:
        print("Skipped full reconciliation test")
        return True

def main():
    """Main test runner"""
    print_header("SALARY RECONCILIATION AGENT - MANUAL TEST")
    
    print("This script will test various components of the agent")
    print("Make sure you have configured the .env file properly")
    print()
    
    input("Press Enter to start testing...")
    
    # Run tests
    tests = [
        ("Configuration", test_configuration),
        ("Directories", test_directories),
        ("Date Logic", test_date_logic),
    ]
    
    for test_name, test_func in tests:
        if not test_func():
            print(f"\n❌ {test_name} test failed. Fix the issues and try again.")
            return
    
    # Optional tests
    print_header("OPTIONAL TESTS")
    print("The following tests are optional and require user confirmation:")
    print()
    
    test_epf_reminder()
    test_full_reconciliation()
    
    print_header("TESTING COMPLETE")
    print("Review the results above. Check logs/ directory for detailed logs.")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
