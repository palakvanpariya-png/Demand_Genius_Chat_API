# app/core/middleware/jwt_middleware.py
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from jose import jwt as jose_jwt, JWTError as JoseJWTError
import pydantic
from loguru import logger

from app.config.settings import settings

security = HTTPBearer()


class JWTAccount(pydantic.BaseModel):
    user_id: str
    tenant_id: str

class JWTMiddleware:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
    
    def retrieve_details_from_token(self, token: str) -> JWTAccount:
        """
        Decode JWT token and extract user details
        
        Args:
            token: JWT token string
            
        Returns:
            JWTAccount with user_id and tenant_id
            
        Raises:
            ValueError: If token is invalid or payload is malformed
        """
        try:
            payload = jose_jwt.decode(
                token=token, 
                key=self.secret_key, 
                algorithms=[settings.JWT_ALGORITHM]
            )
            jwt_account = JWTAccount(
                user_id=payload["user_id"], 
                tenant_id=payload["tenant_id"]
            )
            
        except JoseJWTError as token_decode_error:
            raise ValueError("Unable to decode JWT Token") from token_decode_error
            
        except pydantic.ValidationError as validation_error:
            raise ValueError("Invalid payload in token") from validation_error
            
        except KeyError as key_error:
            raise ValueError(f"Missing required field in token: {key_error}") from key_error
        
        return jwt_account
    
    async def verify_jwt_token(self, request: Request) -> JWTAccount:
        """
        Extract and verify JWT token from request
        
        Args:
            request: FastAPI request object
            
        Returns:
            JWTAccount with user details
            
        Raises:
            HTTPException: If token is missing or invalid
        """
        try:
            # Get Authorization header
            authorization = request.headers.get("Authorization")
            if not authorization:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authorization header missing",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Extract token
            if not authorization.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authorization header format. Use 'Bearer <token>'",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            token = authorization.split("Bearer ")[1]
            
            # Decode and validate token
            jwt_account = self.retrieve_details_from_token(token)
            
            logger.info(f"JWT verified for user: {jwt_account.user_id}, tenant: {jwt_account.tenant_id}")
            return jwt_account
            
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error(f"JWT verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed",
                headers={"WWW-Authenticate": "Bearer"},
            )

# Create global middleware instance
jwt_middleware = JWTMiddleware(secret_key=settings.JWT_SECRET_KEY)

# Dependency function for route protection
async def get_current_user(request: Request) -> JWTAccount:
    """
    Dependency to get current authenticated user from JWT token
    """
    return await jwt_middleware.verify_jwt_token(request)