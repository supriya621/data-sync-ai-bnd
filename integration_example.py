"""
Integration Example: How to save configuration history in your file upload/validation workflow

Add these calls in your existing endpoints where users configure validation rules
"""

# Example: In your file upload endpoint (after user uploads file)
@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        # Your existing file upload logic...
        file = request.files['file']
        
        # Read file and extract headers (your existing code)
        df = pd.read_excel(file, sheet_name=0)  # or pd.read_csv()
        file_headers = df.columns.tolist()
        
        # Save file with timestamp (your existing code)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        internal_file_name = f"{file.filename.split('.')[0]}_{timestamp}.xlsx"
        
        # Get file info
        file_size_mb = len(file.read()) / (1024 * 1024)  # Convert to MB
        file.seek(0)  # Reset file pointer
        total_rows = len(df)
        
        # When user completes rule configuration, save to history
        # This can be in the same endpoint or a separate configuration endpoint
        
        return jsonify({
            'success': True,
            'file_id': internal_file_name,
            'headers': file_headers,
            'file_info': {
                'size_mb': round(file_size_mb, 2),
                'rows': total_rows
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Example: In your rule configuration endpoint (when user assigns rules to columns)
@app.route('/api/configure-rules', methods=['POST'])
def configure_validation_rules():
    try:
        data = request.get_json()
        
        # Your existing rule configuration logic...
        file_id = data.get('file_id')
        configured_rules = data.get('rules', {})  # Format: {"column_name": ["rule1", "rule2"]}
        
        # Example configured_rules format:
        # {
        #   "Name": ["Required", "Text"],
        #   "Email": ["Required", "Email"], 
        #   "Age": ["Required", "Int"],
        #   "Department": ["Text"],
        #   "Salary": ["Required", "Float"]
        # }
        
        # Get file info from your storage/session
        original_file_name = session.get('uploaded_file_name', 'unknown.xlsx')
        file_headers = session.get('file_headers', [])
        sheet_name = session.get('sheet_name', 'Sheet1')
        file_size_mb = session.get('file_size_mb', 0)
        total_rows = session.get('total_rows', 0)
        
        # Save configuration history
        if save_file_configuration_history:  # Check if function is available
            history_id = save_file_configuration_history(
                user_id=session['user_id'],
                file_name=file_id,  # Internal name with timestamp
                original_file_name=original_file_name,  # Original upload name
                file_headers=file_headers,  # List of column names
                configured_rules=configured_rules,  # Rule mappings
                sheet_name=sheet_name,
                file_size_mb=file_size_mb,
                total_rows=total_rows
            )
            
            if history_id:
                logger.info(f"Saved configuration history {history_id} for user {session['user_id']}")
        
        # Your existing response...
        return jsonify({
            'success': True,
            'message': 'Rules configured successfully',
            'history_saved': history_id is not None
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Example: Update validation status when processing completes
@app.route('/api/validate-file', methods=['POST'])  
def validate_file():
    try:
        # Your existing validation logic...
        
        # After validation completes, update the history status
        history_id = request.json.get('history_id')
        if history_id:
            from file_configuration_history import update_file_validation_status
            update_file_validation_status(history_id, 'VALIDATED')
        
        return jsonify({'success': True, 'message': 'File validated'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Example: Simple integration if you want to save history immediately after upload
def simple_integration_example():
    """
    Simple way to integrate: Save basic configuration history right after upload
    Then update with rules when user configures them
    """
    
    # After file upload (minimal info)
    history_id = save_file_configuration_history(
        user_id=session['user_id'],
        file_name="data_20250922_143045.xlsx",  # Internal name
        original_file_name="customer_data.xlsx",  # User's original name  
        file_headers=["Name", "Email", "Age"],  # Extracted from file
        configured_rules={},  # Empty initially
        sheet_name="Sheet1",
        file_size_mb=1.5,
        total_rows=1000
    )
    
    # Later, when user configures rules, update the same record
    # (You'd need to add an update function for this approach)
