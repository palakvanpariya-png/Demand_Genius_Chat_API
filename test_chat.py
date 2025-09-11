# debug_test.py
# Run this from the project root to debug the issue

import sys
import os
sys.path.append(os.getcwd())

from app.core.query_parser import SmartQueryParser
from app.core.advisory_answer import IntelligentAdvisor
from app.core.schema_extractor import get_tenant_schema
from app.config.settings import settings

def test_components():
    print("Testing individual components...")
    
    # Test 1: Schema extraction
    print("\n1. Testing schema extraction...")
    try:
        schema = get_tenant_schema(
            settings.MONGODB_URI, 
            settings.DATABASE_NAME, 
            "6875f3afc8337606d54a7f37"
        )
        print(f"✓ Schema extracted successfully. Categories: {len(schema.get('categories', {}))}")
    except Exception as e:
        print(f"✗ Schema extraction failed: {e}")
        return
    
    # Test 2: Query parsing
    print("\n2. Testing query parsing...")
    try:
        parser = SmartQueryParser()
        result = parser.parse("Hello", "6875f3afc8337606d54a7f37")
        print(f"✓ Query parsed successfully. Operation: {result.operation}")
    except Exception as e:
        print(f"✗ Query parsing failed: {e}")
        return
    
    # Test 3: Advisory generation (this is likely where it fails)
    print("\n3. Testing advisory generation...")
    try:
        advisor = IntelligentAdvisor()
        
        # Create mock data
        mock_query_result = {
            "tenant_id": "6875f3afc8337606d54a7f37",
            "filters": {},
            "operation": "pure_advisory",
            "distribution_fields": [],
            "semantic_terms": [],
            "is_negation": False
        }
        
        mock_db_response = {
            "success": True,
            "data": {"message": "Advisory operation - no database query executed"},
            "advisory_mode": True,
            "operation": "pure_advisory"
        }
        
        response = advisor.generate_advisory_response(
            operation="pure_advisory",
            query_result=mock_query_result,
            db_response=mock_db_response,
            tenant_schema=schema,
            original_query="Hello",
            session_id=None
        )
        print(f"✓ Advisory generated successfully. Response: {response.get('response', '')[:100]}...")
        
    except Exception as e:
        print(f"✗ Advisory generation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n✓ All components working!")

if __name__ == "__main__":
    test_components()