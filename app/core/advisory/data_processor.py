# app/core/advisory/data_processor.py
"""
Data Processor - Handles all data formatting and context building
Uses your proven logic from advisory_engine for data-first approach
"""

from typing import Dict, List, Any, Optional
from loguru import logger

from ...models.query import QueryResult
from ...models.database import DatabaseResponse


class DataProcessor:
    """
    Processes and formats data for advisory agents
    Ensures LLM always sees actual query results
    """
    
    def build_context(
        self,
        operation: str,
        query_result: QueryResult,
        db_response: DatabaseResponse,
        tenant_schema: Dict,
        original_query: str,
        session_id: Optional[str],
        session_handler
    ) -> Dict[str, Any]:
        """
        Build data-first context that guarantees LLM sees actual results
        Uses your proven context building logic
        """
        context = {
            "original_query": original_query,
            "operation": operation,
            "response_type": self._determine_response_type(original_query, operation)
        }
        
        # Add conversation context if available
        if session_id:
            context["previous_context"] = session_handler.get_recent_context(session_id)
        
        # Add actual data results based on operation (critical step)
        if operation in ["list", "semantic"]:
            context["data_results"] = self.format_content_results(db_response)
            
        elif operation == "distribution":
            context["distribution_results"] = self.format_distribution_results(db_response)
            
        else:  # pure_advisory
            context["advisory_context"] = self.format_advisory_context(tenant_schema)
        
        return context
    
    def format_content_results(self, db_response: DatabaseResponse) -> Dict[str, Any]:
        """
        Format content results for LLM with actual numbers
        Uses your proven formatting logic from advisory_engine
        """
        if not db_response.success or not db_response.data:
            return {
                "status": "no_results",
                "total_found": 0,
                "message": "No content matches the search criteria"
            }
        
        total_count = db_response.total_count or len(db_response.data)
        showing_count = len(db_response.data)
        
        return {
            "status": "found_results",
            "total_found": total_count,
            "showing": showing_count,
            "has_more": total_count > showing_count,
            "pagination": {
                "page": db_response.page,
                "total_pages": getattr(db_response, 'total_pages', None)
            } if db_response.page else None
        }
    
    def format_distribution_results(self, db_response: DatabaseResponse) -> Dict[str, Any]:
        """
        Format distribution results with actual percentages and gaps
        Uses your proven distribution analysis from advisory_engine
        """
        if not db_response.success or not db_response.data:
            return {
                "status": "no_distribution",
                "message": "No distribution data available"
            }
        
        # Handle both single and multi-distribution formats
        distributions = []
        
        for item in db_response.data:
            if hasattr(item, 'field'):  # DistributionResult object
                field_name = item.field
                distribution_data = [{"value": d.value, "count": d.count} for d in item.distribution]
                total_items = item.total_items
            elif isinstance(item, dict) and "field" in item:  # Dict format
                field_name = item["field"]
                distribution_data = item.get("distribution", [])
                total_items = item.get("total_items", 0)
            else:  # Simple distribution list
                field_name = "Unknown Category"
                distribution_data = db_response.data if isinstance(db_response.data[0], dict) else []
                total_items = sum(d.get("count", 0) for d in distribution_data)
            
            # Calculate percentages and find gaps using your proven logic
            analysis = self.analyze_distribution(distribution_data, total_items)
            
            distributions.append({
                "category": field_name,
                "total_items": total_items,
                "distribution": distribution_data,
                "analysis": analysis
            })
        
        return {
            "status": "has_distribution",
            "distributions": distributions,
            "total_categories": len(distributions)
        }
    
    def analyze_distribution(self, distribution_data: List[Dict], total_items: int) -> Dict[str, Any]:
        """
        Calculate concrete percentages and identify gaps
        Uses your proven analysis logic from advisory_engine
        """
        if not distribution_data or total_items == 0:
            return {"concentration": "no_data", "top_category": None, "gaps": []}
        
        # Sort by count to find top categories
        sorted_dist = sorted(distribution_data, key=lambda x: x.get("count", 0), reverse=True)
        
        # Calculate percentages
        with_percentages = []
        for item in sorted_dist:
            count = item.get("count", 0)
            percentage = round((count / total_items) * 100, 1) if total_items > 0 else 0
            with_percentages.append({
                "value": item.get("value", "Unknown"),
                "count": count,
                "percentage": percentage
            })
        
        # Determine concentration using your logic
        top_percentage = with_percentages[0]["percentage"] if with_percentages else 0
        if top_percentage > 70:
            concentration = "highly_concentrated"
        elif top_percentage > 40:
            concentration = "moderately_concentrated"
        else:
            concentration = "evenly_distributed"
        
        # Identify gaps (categories with 0 or very low content)
        gaps = [item for item in with_percentages if item["count"] <= 2]
        
        return {
            "concentration": concentration,
            "top_category": with_percentages[0] if with_percentages else None,
            "percentages": with_percentages[:5],  # Top 5 only
            "gaps": gaps[:3]  # Top 3 gaps only
        }
    
    def format_advisory_context(self, tenant_schema: Dict) -> Dict[str, Any]:
        """
        Format context for pure advisory - strategic planning only
        Uses your proven advisory formatting from advisory_engine
        """
        doc_counts = tenant_schema.get("document_counts", {})
        categories = tenant_schema.get("categories", {})
        
        return {
            "status": "advisory_mode",
            "total_content": doc_counts.get("sitemaps", 0),
            "category_structure": categories,  # For strategic context only
            "content_maturity": len(categories)  # How mature their content org is
        }
    
    def _determine_response_type(self, query: str, operation: str) -> str:
        """
        Determine what type of response to generate
        Uses your proven type determination logic
        """
        # Data-driven analysis
        if operation in ["list", "semantic", "distribution"]:
            return "data_analysis"
        
        # Pure advisory
        return "advisory"
    
    def generate_contextual_suggestions(self, context: Dict) -> List[str]:
        """
        Generate relevant follow-up questions based on current context
        Uses your proven suggestion logic from advisory_engine
        """
        operation = context.get("operation", "")
        
        if operation == "list":
            return [
                "How is this content distributed across categories?",
                "What gaps exist in this content area?",
                "Show me the performance metrics for these results"
            ]
        elif operation == "distribution":
            return [
                "Show me specific content in the underrepresented categories",
                "What topics are missing in my top-performing categories?",
                "How can I rebalance this distribution?"
            ]
        else:  # advisory
            return [
                "What's my overall content distribution?",
                "Where are my biggest content gaps?",
                "Show me my top-performing content areas"
            ]