"""
MANUAL PATCH FILE - Apply this fix to your app_redis.py

The issue: Your backend receives rule names ("Text", "Email") from frontend 
but fails to convert them to database IDs (4, 5) before saving.

STEP 1: Add this function near the top of your app_redis.py file (after the imports):
"""

def get_rule_type_id(rule_name):
    """Convert rule name to rule_type_id for database operations"""
    rule_mapping = {
        'Required': 1,
        'Int': 2,
        'Float': 3,
        'Text': 4,
        'Email': 5,
        'Date': 6,
        'Boolean': 7,
        'Alphanumeric': 8
    }
    
    rule_id = rule_mapping.get(rule_name)
    if rule_id is None:
        # Log the error for debugging
        logger.error(f"Unknown rule name received: {rule_name}")
        raise ValueError(f"Unknown rule name: {rule_name}")
    return rule_id

"""
STEP 2: Find your configure_rules function (the one that handles /api/validation/configure-rules)

STEP 3: In that function, replace any INSERT statements to column_validations with this pattern:

OLD CODE (BROKEN):
    # This is what's currently failing:
    fabric_service.execute_non_query(
        "INSERT INTO column_validations (template_id, column_name, rule_type_id) VALUES (?, ?, ?)",
        (template_id, column_name, rule_name)  # <-- This uses rule_name directly (WRONG!)
    )

NEW CODE (FIXED):
    # Convert rule name to ID first:
    rule_type_id = get_rule_type_id(rule_name)
    fabric_service.execute_non_query(
        "INSERT INTO column_validations (template_id, column_name, rule_type_id) VALUES (?, ?, ?)",
        (template_id, column_name, rule_type_id)  # <-- Now uses correct ID
    )

STEP 4: The typical pattern in your function should look like this:

# Process the rules from frontend
validation_data = request.get_json()  # Gets something like: {"name": ["Required", "Text"], "email": ["Required", "Email"]}

# Clear existing rules for this template
fabric_service.execute_non_query(
    "DELETE FROM column_validations WHERE template_id = ?", 
    (template_id,)
)

# Insert new rules with correct IDs
for column_name, rule_names in validation_data.items():
    for rule_name in rule_names:
        try:
            rule_type_id = get_rule_type_id(rule_name)  # <-- ADD THIS LINE
            fabric_service.execute_non_query(
                "INSERT INTO column_validations (template_id, column_name, rule_type_id) VALUES (?, ?, ?)",
                (template_id, column_name, rule_type_id)  # <-- USE rule_type_id, NOT rule_name
            )
        except ValueError as e:
            logger.error(f"Rule mapping error: {e}")
            return jsonify({"success": False, "message": str(e)}), 400

return jsonify({"success": True, "message": "Rules configured successfully"})
"""

STEP 5: Save the file and restart your Flask server.

This will fix the foreign key constraint error because you'll be inserting 
valid rule_type_ids (1-8) instead of invalid rule names.
"""
