"""
Debug Foreign Key Constraint Issue
This script helps identify the specific cause of the foreign key constraint error
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

from backend.config.config import config
from backend.services.fabric_service import fabric_service

def check_foreign_key_constraints():
    """Check all foreign key constraints related to validation rules"""
    print("Checking foreign key constraints...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Get all foreign key constraints
        cursor.execute("""
            SELECT 
                fk.name AS constraint_name,
                tp.name AS parent_table,
                cp.name AS parent_column,
                tr.name AS referenced_table,
                cr.name AS referenced_column
            FROM sys.foreign_keys fk
            INNER JOIN sys.tables tp ON fk.parent_object_id = tp.object_id
            INNER JOIN sys.tables tr ON fk.referenced_object_id = tr.object_id
            INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
            INNER JOIN sys.columns cp ON fkc.parent_column_id = cp.column_id AND fkc.parent_object_id = cp.object_id
            INNER JOIN sys.columns cr ON fkc.referenced_column_id = cr.column_id AND fkc.referenced_object_id = cr.object_id
            WHERE tr.name = 'validation_rule_types' OR tp.name LIKE '%validation%'
        """)
        
        constraints = cursor.fetchall()
        if not constraints:
            print("No foreign key constraints found related to validation rules")
        else:
            print("Foreign key constraints found:")
            for constraint in constraints:
                print(f"  {constraint[0]}: {constraint[1]}.{constraint[2]} -> {constraint[3]}.{constraint[4]}")
        
        cursor.close()
        return constraints
        
    except Exception as e:
        print(f"Error checking constraints: {str(e)}")
        return []

def check_column_validation_table():
    """Check if column_validation table exists and its structure"""
    print("\nChecking column_validation table...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'column_validation'
        """)
        
        if cursor.fetchone()[0] == 0:
            print("column_validation table does not exist")
            return False
        
        # Get table structure
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'column_validation'
            ORDER BY ORDINAL_POSITION
        """)
        
        columns = cursor.fetchall()
        print("column_validation table structure:")
        for col_name, data_type, is_nullable in columns:
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"  {col_name}: {data_type} {nullable}")
        
        # Check data
        cursor.execute("SELECT COUNT(*) FROM column_validation")
        count = cursor.fetchone()[0]
        print(f"column_validation has {count} records")
        
        if count > 0:
            cursor.execute("SELECT TOP 5 * FROM column_validation")
            rows = cursor.fetchall()
            print("Sample data:")
            for row in rows:
                print(f"  {row}")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"Error checking column_validation table: {str(e)}")
        return False

def test_rule_insertion():
    """Test inserting a validation rule to reproduce the error"""
    print("\nTesting validation rule insertion...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Try to insert a test record that might cause the foreign key error
        test_data = {
            'template_id': 999,  # Test template ID
            'column_name': 'test_column',
            'rule_type_id': 1,  # Should exist (Required)
            'parameters': '{}',
            'is_active': 1
        }
        
        cursor.execute("""
            INSERT INTO column_validation 
            (template_id, column_name, rule_type_id, parameters, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, (test_data['template_id'], test_data['column_name'], 
              test_data['rule_type_id'], test_data['parameters'], test_data['is_active']))
        
        conn.commit()
        print("✓ Test insertion successful")
        
        # Clean up test data
        cursor.execute("DELETE FROM column_validation WHERE template_id = 999")
        conn.commit()
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"✗ Test insertion failed: {str(e)}")
        cursor.close()
        return False

def check_specific_constraint_error():
    """Check the specific constraint that's failing"""
    print("\nAnalyzing constraint FK__column_va__rule___7EC1CEDB...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Try to find this specific constraint
        cursor.execute("""
            SELECT 
                fk.name AS constraint_name,
                tp.name AS parent_table,
                cp.name AS parent_column,
                tr.name AS referenced_table,
                cr.name AS referenced_column
            FROM sys.foreign_keys fk
            INNER JOIN sys.tables tp ON fk.parent_object_id = tp.object_id
            INNER JOIN sys.tables tr ON fk.referenced_object_id = tr.object_id
            INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
            INNER JOIN sys.columns cp ON fkc.parent_column_id = cp.column_id AND fkc.parent_object_id = cp.object_id
            INNER JOIN sys.columns cr ON fkc.referenced_column_id = cr.column_id AND fkc.referenced_object_id = cr.object_id
            WHERE fk.name LIKE '%7EC1CEDB%' OR fk.name LIKE 'FK__column_va__rule%'
        """)
        
        constraint_info = cursor.fetchone()
        if constraint_info:
            print(f"Found constraint: {constraint_info[0]}")
            print(f"  Parent: {constraint_info[1]}.{constraint_info[2]}")
            print(f"  References: {constraint_info[3]}.{constraint_info[4]}")
            
            # Check if referenced values exist
            if constraint_info[3] == 'validation_rule_types':
                cursor.execute(f"SELECT DISTINCT {constraint_info[4]} FROM {constraint_info[3]} ORDER BY {constraint_info[4]}")
                valid_values = cursor.fetchall()
                print(f"Valid {constraint_info[4]} values: {[v[0] for v in valid_values]}")
        else:
            print("Specific constraint not found by name pattern")
        
        cursor.close()
        return constraint_info
        
    except Exception as e:
        print(f"Error analyzing constraint: {str(e)}")
        return None

def main():
    """Main debug function"""
    print("=" * 60)
    print("DEBUGGING FOREIGN KEY CONSTRAINT ERROR")
    print("=" * 60)
    
    # Step 1: Check connection
    print("Testing connection...")
    result = fabric_service.test_connection()
    if result['status'] != 'success':
        print(f"✗ Connection failed: {result['message']}")
        return False
    print("✓ Connection successful")
    
    # Step 2: Check foreign key constraints
    check_foreign_key_constraints()
    
    # Step 3: Check column_validation table
    check_column_validation_table()
    
    # Step 4: Check specific failing constraint
    check_specific_constraint_error()
    
    # Step 5: Test insertion
    test_rule_insertion()
    
    print("\n" + "=" * 60)
    print("DEBUG COMPLETE")
    print("=" * 60)
    print("Check the output above to identify the specific issue.")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Debug script failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to exit...")
