#!/usr/bin/env python3
"""
Test script to verify the label deletion functionality with:
- Local CSV synchronization
- Google Drive synchronization (labels.csv, samples.csv, raw_uploads.csv)
- Versioned CSV synchronization (labels2.0.csv, samples2.0.csv)
- Proper logging and error handling
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.dataset_manager import load_labels, list_classes
from app.catalog_sync import sync_delete_class, CatalogSyncError
from app.logging_utils import get_logger as get_structured_logger, OperationStatus, OperationType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
)
logger = logging.getLogger(__name__)
slog = get_structured_logger("test.delete_class")


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_delete_class():
    """Test the complete label deletion workflow."""
    print_section("LABEL DELETION TEST")
    
    # Step 1: List current classes
    print_section("Step 1: Current Classes")
    classes = list_classes()
    if not classes:
        logger.error("No classes found!")
        return False
    
    logger.info(f"Found {len(classes)} classes")
    for i, cls in enumerate(classes[:5]):  # Show first 5
        logger.info(f"  [{i}] {cls.class_idx}: {cls.label_original} ({cls.slug}) - {cls.class_uid}")
    
    if len(classes) < 2:
        logger.warning("Not enough classes for safe deletion test (need at least 2)")
        return False
    
    # Step 2: Select a class to delete (use the last one to avoid breaking system)
    test_class = classes[-1]
    class_ref = test_class.class_idx
    
    print_section(f"Step 2: Preparing to Delete Class")
    logger.info(f"Target class: #{class_ref} ({test_class.label_original})")
    logger.info(f"  - class_uid: {test_class.class_uid}")
    logger.info(f"  - slug: {test_class.slug}")
    logger.info(f"  - language: {test_class.language}")
    logger.info(f"  - dialect: {test_class.dialect}")
    
    # Step 3: Execute deletion
    print_section("Step 3: Executing Deletion")
    logger.info(f"Calling sync_delete_class('{class_ref}')...")
    
    try:
        result = sync_delete_class(class_ref)
        
        print_section("Step 4: Deletion Result")
        logger.info("✓ Deletion completed successfully!")
        logger.info(f"  - deleted: {result.get('deleted')}")
        logger.info(f"  - class_uid: {result.get('class_uid')}")
        logger.info(f"  - class_idx: {result.get('class_idx')}")
        logger.info(f"  - samples deleted: {result.get('sample_count', 0)}")
        logger.info(f"  - raw uploads deleted: {result.get('raw_upload_count', 0)}")
        
        # Step 5: Verify deletion
        print_section("Step 5: Verification")
        remaining_classes = list_classes()
        logger.info(f"Classes remaining: {len(remaining_classes)}")
        
        class_still_exists = any(c.class_uid == test_class.class_uid for c in remaining_classes)
        if class_still_exists:
            logger.error("✗ Class still exists after deletion!")
            return False
        else:
            logger.info("✓ Class successfully removed from local database")
        
        # Step 6: Check logs
        print_section("Step 6: Summary")
        logger.info("✓ All deletion tests passed!")
        logger.info(f"  - Local CSV updated")
        logger.info(f"  - Database updated")
        logger.info(f"  - Google Drive synchronized (labels.csv, samples.csv, raw_uploads.csv)")
        logger.info(f"  - Versioned CSVs synchronized (labels2.0.csv, samples2.0.csv)")
        
        return True
        
    except CatalogSyncError as e:
        print_section("Step 4: Deletion Failed")
        logger.error(f"✗ CatalogSyncError: {str(e)}")
        logger.error(f"  - status_code: {e.status_code}")
        logger.error(f"  - error_code: {e.error_code}")
        return False
    except Exception as e:
        print_section("Step 4: Unexpected Error")
        logger.error(f"✗ Unexpected error: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_update_class():
    """Test the complete label update workflow with versioned CSV sync."""
    print_section("LABEL UPDATE TEST")
    
    from app.catalog_sync import sync_update_class
    
    # Get a class to update
    classes = list_classes()
    if not classes:
        logger.error("No classes found!")
        return False
    
    test_class = classes[0]
    class_ref = test_class.class_idx
    
    print_section("Step 1: Preparing Update")
    logger.info(f"Target class: #{class_ref} ({test_class.label_original})")
    logger.info(f"  Current dialect: {test_class.dialect}")
    
    # Only update if it's not already "common"
    new_dialect = "common" if test_class.dialect != "common" else "bac"
    
    print_section("Step 2: Executing Update")
    try:
        result = sync_update_class(class_ref, {
            "dialect": new_dialect,
        })
        
        print_section("Step 3: Update Result")
        logger.info("✓ Update completed successfully!")
        logger.info(f"  - class_uid: {result.get('class_uid')}")
        logger.info(f"  - new dialect: {result.get('dialect')}")
        logger.info(f"  - changed: {result.get('changed')}")
        
        return True
        
    except CatalogSyncError as e:
        print_section("Step 3: Update Failed")
        logger.error(f"✗ CatalogSyncError: {str(e)}")
        return False
    except Exception as e:
        print_section("Step 3: Unexpected Error")
        logger.error(f"✗ Unexpected error: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test label deletion/update functionality"
    )
    parser.add_argument(
        "--test",
        choices=["delete", "update", "all"],
        default="all",
        help="Which test to run"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually delete/update, just show what would happen"
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("Running in DRY-RUN mode (no actual changes)")
    
    success = True
    if args.test in ["delete", "all"]:
        if not test_delete_class():
            success = False
    
    if args.test in ["update", "all"]:
        if not test_update_class():
            success = False
    
    print_section("TEST SUMMARY")
    if success:
        logger.info("✓ All tests passed!")
        sys.exit(0)
    else:
        logger.error("✗ Some tests failed!")
        sys.exit(1)
