# Add this endpoint to your app.py to check if user has configured rules

@app.route('/api/validation/check-rules', methods=['GET'])
@login_required
def check_configured_rules():
    """Check if user has any configured validation rules"""
    try:
        user_id = session['user_id']
        
        # Check if user has any templates with configured rules
        templates = fabric_service.execute_query("""
            SELECT COUNT(DISTINCT t.template_id) as template_count
            FROM excel_templates t
            JOIN template_columns tc ON t.template_id = tc.template_id
            JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            WHERE t.user_id = ? AND t.status = 'ACTIVE'
        """, (user_id,))
        
        has_rules = templates[0]['template_count'] > 0 if templates else False
        
        return jsonify({
            'success': True,
            'has_configured_rules': has_rules,
            'template_count': templates[0]['template_count'] if templates else 0
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking configured rules: {e}")
        return jsonify({
            'success': True, 
            'has_configured_rules': False,  # Default to false on error
            'template_count': 0
        }), 200