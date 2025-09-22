"""
Integration script to add Configuration History routes to the main app
This will add the history functionality without disrupting existing code
"""

# Configuration History Routes - Add these to app_redis.py after the existing routes

config_history_routes = '''
# Configuration History Routes - Rule Configuration History Management
@app.route('/api/config-history', methods=['GET'])
@login_required
@monitor_api_performance("get_configuration_history")
def get_configuration_history():
    """Get rule configuration history for the current user"""
    try:
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Get configuration history with enriched data
        history_query = """
            SELECT 
                rch.history_id,
                rch.user_id,
                rch.template_id,
                rch.file_name,
                rch.original_file_name,
                rch.sheet_name,
                rch.total_rules_configured,
                rch.configured_columns_count,
                rch.configuration_summary,
                rch.file_size_mb,
                rch.total_rows,
                rch.created_at,
                rch.updated_at,
                rch.is_active,
                et.status as template_status
            FROM rule_configuration_history rch
            LEFT JOIN excel_templates et ON rch.template_id = et.template_id
            WHERE rch.user_id = ? AND rch.is_active = 1
            ORDER BY rch.updated_at DESC, rch.created_at DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        
        history_records = fabric_service.execute_query(
            history_query, 
            (session['user_id'], offset, limit)
        )
        
        # Get total count
        count_query = """
            SELECT COUNT(*) as total
            FROM rule_configuration_history rch
            WHERE rch.user_id = ? AND rch.is_active = 1
        """
        total_count = fabric_service.execute_query(count_query, (session['user_id'],))
        total = total_count[0]['total'] if total_count else 0
        
        # Enrich each record with additional information
        enriched_history = []
        for record in history_records:
            # Check if template still exists
            template_exists = record.get('template_status') == 'ACTIVE'
            
            # Get detailed rule information if template exists
            rule_details = []
            if template_exists and record['configuration_summary']:
                try:
                    detailed_rules = fabric_service.execute_query("""
                        SELECT 
                            tc.column_name,
                            vrt.rule_name,
                            vrt.description
                        FROM template_columns tc
                        JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
                        JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
                        WHERE tc.template_id = ? AND tc.is_selected = 1
                        ORDER BY tc.column_position
                    """, (record['template_id'],))
                    
                    # Group rules by column
                    rules_by_column = {}
                    for rule in detailed_rules:
                        col_name = rule['column_name']
                        if col_name not in rules_by_column:
                            rules_by_column[col_name] = []
                        rules_by_column[col_name].append({
                            'rule_name': rule['rule_name'],
                            'description': rule['description']
                        })
                    rule_details = rules_by_column
                except Exception as e:
                    logger.warning(f"Failed to get detailed rules for template {record['template_id']}: {e}")
            
            enriched_record = {
                'history_id': record['history_id'],
                'template_id': record['template_id'],
                'file_name': record['original_file_name'],  # Show original name to user
                'sheet_name': record['sheet_name'],
                'total_rules_configured': record['total_rules_configured'],
                'configured_columns_count': record['configured_columns_count'],
                'file_size_mb': round(record['file_size_mb'], 2) if record['file_size_mb'] else 0,
                'total_rows': record['total_rows'] or 0,
                'configured_date': record['created_at'].strftime('%Y-%m-%d %H:%M') if record['created_at'] else '',
                'last_updated': record['updated_at'].strftime('%Y-%m-%d %H:%M') if record['updated_at'] else '',
                'can_reconfigure': template_exists,
                'can_validate': template_exists and record['total_rules_configured'] > 0,
                'template_exists': template_exists,
                'rule_details': rule_details,
                'status': 'Ready' if (template_exists and record['total_rules_configured'] > 0) else 'Incomplete'
            }
            enriched_history.append(enriched_record)
        
        response_data = {
            'success': True,
            'history': enriched_history,
            'pagination': {
                'total': total,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total
            },
            'performance': {
                'cache_enabled': REDIS_AVAILABLE,
                'records_found': len(enriched_history)
            }
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error getting configuration history: {e}")
        return jsonify({'success': False, 'message': 'Failed to get configuration history'}), 500

@app.route('/api/config-history/<int:history_id>/reconfigure', methods=['POST'])
@login_required
@monitor_api_performance("start_reconfiguration")
def start_reconfiguration(history_id):
    """Start reconfiguration process for a historical configuration"""
    try:
        # Get history record
        history_query = """
            SELECT 
                rch.template_id,
                rch.file_name,
                rch.original_file_name,
                et.template_name,
                et.sheet_name,
                et.headers
            FROM rule_configuration_history rch
            JOIN excel_templates et ON rch.template_id = et.template_id
            WHERE rch.history_id = ? AND rch.user_id = ? AND rch.is_active = 1
        """
        
        history_records = fabric_service.execute_query(
            history_query, 
            (history_id, session['user_id'])
        )
        
        if not history_records:
            return jsonify({'success': False, 'message': 'Configuration history not found'}), 404
        
        record = history_records[0]
        template_id = record['template_id']
        
        # Set up session for reconfiguration
        session['reconfigure_mode'] = True
        session['reconfigure_history_id'] = history_id
        session['reconfigure_template_id'] = template_id
        session['current_template_id'] = template_id
        session['headers'] = json.loads(record['headers']) if record['headers'] else []
        
        response_data = {
            'success': True,
            'message': 'Reconfiguration started',
            'reconfigure_context': {
                'history_id': history_id,
                'template_id': template_id,
                'file_name': record['original_file_name'],
                'sheet_name': record['sheet_name'],
                'headers': session['headers'],
                'redirect_to': '/rule-configuration'
            },
            'performance': {
                'cache_enabled': REDIS_AVAILABLE
            }
        }
        
        logger.info(f"Started reconfiguration for history_id {history_id}, template_id {template_id}")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error starting reconfiguration for history_id {history_id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to start reconfiguration'}), 500

@app.route('/api/config-history/<int:history_id>', methods=['DELETE'])
@login_required
@monitor_api_performance("delete_configuration_history")
def delete_configuration_history(history_id):
    """Delete configuration history record (soft delete)"""
    try:
        # Verify ownership
        history_query = """
            SELECT template_id, file_name
            FROM rule_configuration_history
            WHERE history_id = ? AND user_id = ? AND is_active = 1
        """
        
        history_records = fabric_service.execute_query(
            history_query, 
            (history_id, session['user_id'])
        )
        
        if not history_records:
            return jsonify({'success': False, 'message': 'Configuration history not found'}), 404
        
        record = history_records[0]
        
        # Soft delete the history record
        delete_query = """
            UPDATE rule_configuration_history
            SET is_active = 0, updated_at = GETDATE()
            WHERE history_id = ? AND user_id = ?
        """
        
        fabric_service.execute_non_query(delete_query, (history_id, session['user_id']))
        
        logger.info(f"Deleted configuration history {history_id}")
        return jsonify({
            'success': True, 
            'message': 'Configuration history deleted successfully',
            'performance': {
                'cache_enabled': REDIS_AVAILABLE
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting configuration history {history_id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to delete configuration history'}), 500

@app.route('/api/config-history/<int:history_id>/validate', methods=['POST'])
@login_required
@monitor_api_performance("start_validation_from_history")
def start_validation_from_history(history_id):
    """Start data validation directly from configuration history"""
    try:
        # Get history record with template info
        history_query = """
            SELECT 
                rch.template_id,
                rch.file_name,
                rch.original_file_name,
                rch.total_rules_configured,
                et.template_name,
                et.sheet_name,
                et.headers,
                et.status
            FROM rule_configuration_history rch
            JOIN excel_templates et ON rch.template_id = et.template_id
            WHERE rch.history_id = ? AND rch.user_id = ? AND rch.is_active = 1
        """
        
        history_records = fabric_service.execute_query(
            history_query, 
            (history_id, session['user_id'])
        )
        
        if not history_records:
            return jsonify({'success': False, 'message': 'Configuration history not found'}), 404
        
        record = history_records[0]
        
        # Verify template is active and has rules
        if record['status'] != 'ACTIVE':
            return jsonify({'success': False, 'message': 'Template is no longer active'}), 400
        
        if record['total_rules_configured'] == 0:
            return jsonify({'success': False, 'message': 'No validation rules configured for this template'}), 400
        
        # Set up session for validation
        session['validation_template_id'] = record['template_id']
        session['validation_from_history'] = True
        session['validation_history_id'] = history_id
        
        response_data = {
            'success': True,
            'message': 'Ready for data validation',
            'validation_context': {
                'template_id': record['template_id'],
                'history_id': history_id,
                'file_name': record['original_file_name'],
                'sheet_name': record['sheet_name'],
                'total_rules': record['total_rules_configured'],
                'redirect_to': '/data-validation'
            },
            'performance': {
                'cache_enabled': REDIS_AVAILABLE
            }
        }
        
        logger.info(f"Started validation from history_id {history_id}, template_id {record['template_id']}")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error starting validation from history_id {history_id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to start validation from history'}), 500

# Configuration History Helper Functions
def save_configuration_history(template_id, user_id, file_name, original_file_name, sheet_name=None, file_size_mb=None, total_rows=None):
    """
    Save or update configuration history when rules are configured
    This function is called from the rule configuration process
    """
    try:
        # Check if history record already exists for this template
        existing_query = """
            SELECT history_id FROM rule_configuration_history
            WHERE template_id = ? AND user_id = ? AND is_active = 1
        """
        existing_records = fabric_service.execute_query(existing_query, (template_id, user_id))
        
        if existing_records:
            # Update existing record
            history_id = existing_records[0]['history_id']
            
            # Get current rule configuration
            rule_summary = get_rule_configuration_summary(template_id)
            
            update_query = """
                UPDATE rule_configuration_history
                SET 
                    total_rules_configured = ?,
                    configured_columns_count = ?,
                    configuration_summary = ?,
                    file_size_mb = COALESCE(?, file_size_mb),
                    total_rows = COALESCE(?, total_rows),
                    updated_at = GETDATE()
                WHERE history_id = ?
            """
            
            fabric_service.execute_non_query(update_query, (
                rule_summary['total_rules'],
                rule_summary['column_count'],
                rule_summary['summary'],
                file_size_mb,
                total_rows,
                history_id
            ))
            
            logger.info(f"Updated configuration history {history_id} for template {template_id}")
            return history_id
        else:
            # Create new history record
            rule_summary = get_rule_configuration_summary(template_id)
            
            insert_query = """
                INSERT INTO rule_configuration_history (
                    user_id, template_id, file_name, original_file_name, sheet_name,
                    total_rules_configured, configured_columns_count, configuration_summary,
                    file_size_mb, total_rows, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())
            """
            
            fabric_service.execute_non_query(insert_query, (
                user_id, template_id, file_name, original_file_name, sheet_name,
                rule_summary['total_rules'], rule_summary['column_count'], rule_summary['summary'],
                file_size_mb, total_rows
            ))
            
            # Get the new history_id
            new_record = fabric_service.execute_query("""
                SELECT TOP 1 history_id FROM rule_configuration_history
                WHERE template_id = ? AND user_id = ?
                ORDER BY created_at DESC
            """, (template_id, user_id))
            
            history_id = new_record[0]['history_id'] if new_record else None
            logger.info(f"Created new configuration history {history_id} for template {template_id}")
            return history_id
            
    except Exception as e:
        logger.error(f"Error saving configuration history for template {template_id}: {e}")
        return None

def get_rule_configuration_summary(template_id):
    """Get summary of configured rules for a template"""
    try:
        rules_query = """
            SELECT 
                tc.column_name,
                vrt.rule_name,
                COUNT(*) OVER() as total_count,
                COUNT(DISTINCT tc.column_id) OVER() as column_count
            FROM template_columns tc
            JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
            WHERE tc.template_id = ? AND tc.is_selected = 1
        """
        
        rules = fabric_service.execute_query(rules_query, (template_id,))
        
        if not rules:
            return {
                'total_rules': 0,
                'column_count': 0,
                'summary': ''
            }
        
        # Build summary string
        rules_by_column = {}
        for rule in rules:
            col_name = rule['column_name']
            if col_name not in rules_by_column:
                rules_by_column[col_name] = []
            rules_by_column[col_name].append(rule['rule_name'])
        
        summary_parts = []
        for col_name, rule_names in rules_by_column.items():
            summary_parts.append(f"{col_name}: {', '.join(rule_names)}")
        
        return {
            'total_rules': rules[0]['total_count'],
            'column_count': rules[0]['column_count'],
            'summary': '; '.join(summary_parts)
        }
        
    except Exception as e:
        logger.error(f"Error getting rule summary for template {template_id}: {e}")
        return {
            'total_rules': 0,
            'column_count': 0,
            'summary': ''
        }
'''

print("Configuration History Routes Ready!")
print("\\nTo integrate:")
print("1. First run: python create_configuration_history_table.py")
print("2. Add the routes above to your app_redis.py file")
print("3. Add the save_configuration_history() call to your rule configuration endpoint")
print("4. Restart your Flask server")
