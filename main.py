"""
Main Salary Reconciliation Agent - IMPROVED VERSION
Orchestrates the entire reconciliation workflow with smart file detection
"""

import os
import logging
from pathlib import Path
from datetime import datetime
import glob
import time

from config import Config
from rms_automation import RMSAutomation
from data_processor import DataProcessor
from reconciliation_engine import ReconciliationEngine
from email_handler import EmailHandler

# Setup logging
def setup_logging():
    """Configure logging for the application"""
    os.makedirs(Config.LOGS_DIR, exist_ok=True)
    
    log_file = Path(Config.LOGS_DIR) / f"reconciliation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

logger = setup_logging()

class SalaryReconciliationAgent:
    
    def __init__(self):
        self.config = Config
        self.rms = None
        self.email_handler = EmailHandler()
        
        # Create necessary directories
        os.makedirs(Config.DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(Config.EPF_UPLOAD_DIR, exist_ok=True)
        os.makedirs(Config.REPORTS_DIR, exist_ok=True)
        os.makedirs(Config.LOGS_DIR, exist_ok=True)
    
    def send_epf_reminder(self):
        """Send EPF upload reminder (runs on 16th)"""
        try:
            logger.info("=" * 80)
            logger.info("SENDING EPF UPLOAD REMINDER")
            logger.info("=" * 80)
            
            success = self.email_handler.send_epf_reminder()
            
            if success:
                logger.info("EPF reminder sent successfully")
            else:
                logger.error("Failed to send EPF reminder")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending EPF reminder: {str(e)}")
            return False
    
    def download_files_from_rms(self):
        """Download all required files from RMS portal"""
        try:
            logger.info("=" * 80)
            logger.info("DOWNLOADING FILES FROM RMS")
            logger.info("=" * 80)
            
            # Get target months
            target_months = Config.get_target_months()
            logger.info(f"Salary/TDS/EPF Month: {target_months['salary_month_str']}")
            logger.info(f"Bank SOA Month: {target_months['bank_month_str']}")
            
            # Initialize RMS automation
            self.rms = RMSAutomation()
            self.rms.setup_driver()
            
            # Login to RMS
            if not self.rms.login():
                raise Exception("Failed to login to RMS portal")
            
            # Download Salary Sheet
            logger.info("Downloading Salary Sheet...")
            if not self.rms.download_salary_sheet(target_months['salary_month_value']):
                raise Exception("Failed to download Salary Sheet")
            
            # Wait for download to complete
            time.sleep(5)
            
            # Download TDS Sheet
            logger.info("Downloading TDS Sheet...")
            if not self.rms.download_tds_sheet(target_months['salary_month_value']):
                raise Exception("Failed to download TDS Sheet")
            
            # Wait for download to complete
            time.sleep(5)
            
            # Download Bank SOA
            logger.info("Downloading Bank SOA...")
            if not self.rms.download_bank_soa(
                target_months['bank_start_date'],
                target_months['bank_end_date']
            ):
                raise Exception("Failed to download Bank SOA")
            
            # Wait for download to complete
            time.sleep(5)
            
            logger.info("All files downloaded successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Error downloading files: {str(e)}")
            return False
        
        finally:
            if self.rms:
                self.rms.close()
    
    def smart_file_detection(self, directory):
        """
        Intelligently detect files based on actual filenames from RMS
        Returns a dict with detected file paths
        """
        files = {}
        
        # Get all Excel files
        all_excel = sorted(
            glob.glob(str(Path(directory) / "*.xlsx")) + 
            glob.glob(str(Path(directory) / "*.xls")),
            key=os.path.getctime,
            reverse=True
        )
        
        logger.info(f"\nFound {len(all_excel)} Excel files in downloads directory:")
        for idx, f in enumerate(all_excel):
            filename = os.path.basename(f)
            filesize = os.path.getsize(f)
            logger.info(f"  {idx+1}. {filename} ({filesize:,} bytes)")
        
        # Detect files by name patterns
        for file in all_excel:
            filename_lower = os.path.basename(file).lower()
            
            # Salary Sheet patterns (note the typo "Salay_Sheet" from RMS)
            if 'salay_sheet' in filename_lower or 'salary_sheet' in filename_lower:
                if 'salary' not in files:
                    files['salary'] = file
                    logger.info(f"\n✓ Detected SALARY file: {os.path.basename(file)}")
            
            # TDS Sheet patterns
            elif 'update tds' in filename_lower or 'updatetds' in filename_lower:
                if 'tds' not in files:
                    files['tds'] = file
                    logger.info(f"✓ Detected TDS file: {os.path.basename(file)}")
            
            # Bank SOA patterns
            elif 'bankbook' in filename_lower or ('bank' in filename_lower and 'uploaded' in filename_lower):
                if 'bank' not in files:
                    files['bank'] = file
                    logger.info(f"✓ Detected BANK file: {os.path.basename(file)}")
        
        return files
    
    def find_epf_file(self):
        """Find the EPF file in upload directory"""
        # Look for Excel files in EPF upload directory
        excel_files = glob.glob(str(Path(Config.EPF_UPLOAD_DIR) / "*.xlsx"))
        excel_files.extend(glob.glob(str(Path(Config.EPF_UPLOAD_DIR) / "*.xls")))
        
        if not excel_files:
            logger.warning("No EPF file found in upload directory")
            return None
        
        # Return the most recent file
        latest_file = max(excel_files, key=os.path.getctime)
        logger.info(f"Found EPF file: {latest_file}")
        return latest_file
    
    def process_files(self):
        """Process all downloaded files"""
        try:
            logger.info("=" * 80)
            logger.info("PROCESSING FILES")
            logger.info("=" * 80)
            
            # Use smart file detection
            detected_files = self.smart_file_detection(Config.DOWNLOAD_DIR)
            
            # Get file paths
            salary_file = detected_files.get('salary')
            tds_file = detected_files.get('tds')
            bank_file = detected_files.get('bank')
            epf_file = self.find_epf_file()
            
            # Validate files exist
            missing_files = []
            if not salary_file:
                missing_files.append("Salary Sheet")
            if not tds_file:
                missing_files.append("TDS Sheet")
            if not bank_file:
                missing_files.append("Bank SOA")
            if not epf_file:
                missing_files.append("EPF file")
            
            if missing_files:
                error_msg = f"Missing files: {', '.join(missing_files)}"
                logger.error(error_msg)
                logger.info("\nPlease check:")
                logger.info("1. Files were downloaded successfully from RMS")
                logger.info("2. EPF file was uploaded to epf_uploads/ directory")
                logger.info("3. File names match expected patterns")
                raise Exception(error_msg)
            
            logger.info("\n" + "=" * 60)
            logger.info("FILES TO PROCESS:")
            logger.info(f"  Salary: {os.path.basename(salary_file)}")
            logger.info(f"  TDS:    {os.path.basename(tds_file)}")
            logger.info(f"  Bank:   {os.path.basename(bank_file)}")
            logger.info(f"  EPF:    {os.path.basename(epf_file)}")
            logger.info("=" * 60 + "\n")
            
            # Process each file
            logger.info("Processing Salary Sheet...")
            salary_data = DataProcessor.process_salary_sheet(salary_file)
            
            logger.info("Processing TDS Sheet...")
            tds_data = DataProcessor.process_tds_sheet(tds_file)
            
            logger.info("Processing Bank SOA...")
            bank_data = DataProcessor.process_bank_soa(bank_file)
            
            logger.info("Processing EPF Sheet...")
            epf_data = DataProcessor.process_epf_sheet(epf_file)
            
            return salary_data, tds_data, bank_data, epf_data
            
        except Exception as e:
            logger.error(f"Error processing files: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def perform_reconciliation(self, salary_data, tds_data, bank_data, epf_data):
        """Perform reconciliation and generate reports"""
        try:
            logger.info("=" * 80)
            logger.info("PERFORMING RECONCILIATION")
            logger.info("=" * 80)
            
            # Initialize reconciliation engine
            engine = ReconciliationEngine(salary_data, tds_data, bank_data, epf_data)
            
            # Run reconciliation
            reconciled_data = engine.reconcile()
            
            # Generate reports
            target_months = Config.get_target_months()
            report_filename = f"Salary_Reconciliation_{target_months['salary_month'].strftime('%B_%Y')}.xlsx"
            report_file = Path(Config.REPORTS_DIR) / report_filename
            
            engine.save_reports(str(report_file))
            
            # Get summary for email
            summary = engine.generate_summary_report().iloc[0].to_dict()
            
            return report_file, summary
            
        except Exception as e:
            logger.error(f"Error during reconciliation: {str(e)}")
            raise
    
    def run_full_reconciliation(self):
        """Run the complete reconciliation process (runs on 17th)"""
        try:
            logger.info("=" * 80)
            logger.info("STARTING SALARY RECONCILIATION AGENT")
            logger.info(f"Date: {datetime.now().strftime('%d %B %Y at %I:%M %p')}")
            logger.info("=" * 80)
            
            # Step 1: Download files from RMS
            if not self.download_files_from_rms():
                raise Exception("Failed to download files from RMS")
            
            # Step 2: Process downloaded files
            salary_data, tds_data, bank_data, epf_data = self.process_files()
            
            # Step 3: Perform reconciliation
            report_file, summary = self.perform_reconciliation(
                salary_data, tds_data, bank_data, epf_data
            )
            
            # Step 4: Send email with results
            logger.info("=" * 80)
            logger.info("SENDING RECONCILIATION REPORT")
            logger.info("=" * 80)
            
            success = self.email_handler.send_reconciliation_report(
                report_file=str(report_file),
                summary_data=summary
            )

            if success:
                logger.info("Reconciliation report sent successfully")
            else:
                logger.error("Failed to send reconciliation report")
            
            logger.info("=" * 80)
            logger.info("RECONCILIATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            
            return True
            
        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"RECONCILIATION FAILED: {str(e)}")
            logger.error("=" * 80)
            
            import traceback
            logger.error(traceback.format_exc())
            
            # Send error notification email
            try:
                self.email_handler.send_error_notification(str(e))
            except:
                pass
            
            return False

def main():
    """Main entry point"""
    agent = SalaryReconciliationAgent()
    
    # Check if this is a test run
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        print("\n" + "=" * 80)
        print("RUNNING TEST MODE")
        print("=" * 80)
        return agent.run_full_reconciliation()
    
    # Normal run
    return agent.run_full_reconciliation()

if __name__ == "__main__":
    main()
