# app/core/helpers/database_helpers.py
from typing import Dict, List
from bson import ObjectId
from loguru import logger

def get_standardized_lookup_pipeline() -> List[Dict]:
    """
    Get standardized lookup pipeline that produces the expected data format
    Based on the reference getAllSitemap function
    """
    return [
        # Lookup category attributes with nested category information
        {
            "$lookup": {
                "from": "category-attributes",
                "localField": "categoryAttribute",
                "foreignField": "_id",
                "as": "categoryAttribute",
                "pipeline": [
                    {
                        "$lookup": {
                            "from": "categories",
                            "localField": "category",
                            "foreignField": "_id",
                            "as": "category"
                        }
                    },
                    {
                        "$unwind": {
                            "path": "$category"
                        }
                    }
                ]
            }
        }
    ]

def get_category_attribute_ids(db, names: List[str], category_name: str, tenant_id: str) -> List[ObjectId]:
    """Get category attribute ObjectIds for specific category"""
    if not names:
        return []
    
    tenant_obj_id = ObjectId(tenant_id)
    
    # Get category ObjectId
    category_doc = db.categories.find_one({
        "name": category_name,
        "tenant": tenant_obj_id
    })
    
    if not category_doc:
        logger.warning(f"Category not found: {category_name}")
        return []
    
    # Get attribute ObjectIds
    attrs = list(db.category_attributes.find({
        "name": {"$in": names},
        "category": category_doc["_id"],
        "tenant": tenant_obj_id
    }, {"_id": 1}))
    
    found_ids = [attr["_id"] for attr in attrs]
    logger.debug(f"Found {len(found_ids)} attribute IDs for {category_name}: {names}")
    return found_ids

def get_reference_ids(db, collection: str, names: List[str], tenant_id: str) -> List[ObjectId]:
    """Get ObjectIds from reference collections"""
    if not names:
        return []
    
    docs = list(db[collection].find({
        "name": {"$in": names},
        "tenant": ObjectId(tenant_id)
    }, {"_id": 1}))
    
    return [doc["_id"] for doc in docs]

def get_count(db, match_query: Dict) -> int:
    """Get document count for match query"""
    count_result = list(db.sitemaps.aggregate([
        {"$match": match_query},
        {"$count": "total"}
    ]))
    return count_result[0]["total"] if count_result else 0