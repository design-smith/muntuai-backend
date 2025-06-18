from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWSError, JWSAlgorithmError
import os

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPABASE_JWT_ALG = os.getenv("SUPABASE_JWT_ALG", "HS256")

# Supabase JWTs for authenticated users typically have an audience of "authenticated"
SUPABASE_AUDIENCE = os.getenv("SUPABASE_AUDIENCE", "authenticated") 


# Basic validation for essential environment variables
if not SUPABASE_JWT_SECRET:
    raise ValueError("SUPABASE_JWT_SECRET environment variable is not set.")
if not SUPABASE_JWT_ALG:
    raise ValueError("SUPABASE_JWT_ALG environment variable is not set.")

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependency to get the current authenticated user from a JWT.

    Raises:
        HTTPException:
            - 401 Unauthorized if the token is missing, invalid, expired,
              or has incorrect claims (including audience).
    """
    print("DEBUG: [get_current_user] Function entered.")
    token = credentials.credentials
    print(f"DEBUG: [get_current_user] Attempting to decode JWT: {token[:30]}...")
    print(f"DEBUG: [get_current_user] Using secret: {SUPABASE_JWT_SECRET[:5]}..., algorithms: {[SUPABASE_JWT_ALG]}, audience: {SUPABASE_AUDIENCE}")
    
    try:
        payload = jwt.decode(
            token, 
            SUPABASE_JWT_SECRET, 
            algorithms=[SUPABASE_JWT_ALG],
            audience=SUPABASE_AUDIENCE
        )
        print(f"DEBUG: [get_current_user] Decoded JWT payload: {payload}")
        
        user_id = payload.get("sub")
        email = payload.get("email")
        print(f"DEBUG: [get_current_user] Extracted user_id: {user_id}, email: {email}")
        
        if not user_id:
            print("DEBUG: [get_current_user] JWT payload missing 'sub' claim. Raising 401.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials: Missing user identifier."
            )
        
        print(f"DEBUG: [get_current_user] Successfully extracted user_id and email. Returning user object.")
        return {"user_id": user_id, "email": email, "user": payload}
    except JWTError as e:
        print(f"ERROR: [get_current_user] JWTError encountered: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials."
        )
    except Exception as e:
        print(f"ERROR: [get_current_user] An unexpected error occurred: {e}")
        import traceback
        print(f"TRACEBACK: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication."
        )