from datetime import datetime
from loguru import logger

def parse_date_string(date_string: str) -> datetime:
    """Parse date string handling different formats"""
    try:
        # Try ISO format first (with time)
        return datetime.fromisoformat(date_string)
    except ValueError:
        try:
            # Try date-only format (YYYY-MM-DD)
            return datetime.strptime(date_string, '%Y-%m-%d')
        except ValueError:
            # Try other common formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d', '%m/%d/%Y']:
                try:
                    return datetime.strptime(date_string, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Unable to parse date format: {date_string}")