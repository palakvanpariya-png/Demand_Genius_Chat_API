from datetime import datetime, timezone
from loguru import logger

def parse_date_string(date_string: str) -> datetime:
    """Parse date string and return timezone-aware datetime"""
    try:
        dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        try:
            dt = datetime.strptime(date_string, '%Y-%m-%d')
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d', '%m/%d/%Y']:
                try:
                    dt = datetime.strptime(date_string, fmt)
                    return dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            raise ValueError(f"Unable to parse date format: {date_string}")