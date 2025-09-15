import jwt
from datetime import datetime, timedelta, timezone

payload = {
    'user_id': 'user_123',
    'tenant_id': '6875f3afc8337606d54a7f37',
    'iat': int(datetime.now(timezone.utc).timestamp()),
    'exp': int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
}

token = jwt.encode(payload, 'your-secret-key-here', algorithm='HS256')
print(token)