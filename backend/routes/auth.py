import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from databases.database import get_db
from auth_utils import hash_password, verify_password, create_access_token, get_current_user
from fastapi import Depends

router = APIRouter(prefix="/auth", tags=["Auth"])


class SignupRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthOut(BaseModel):
    token: str
    user_id: str
    email: str
    name: str
    tier: str


@router.post("/signup", response_model=AuthOut)
def signup(body: SignupRequest):
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    conn   = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (body.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user_id       = str(uuid.uuid4())
    password_hash = hash_password(body.password)
    name          = body.name.strip() or body.email.split("@")[0]

    cursor.execute(
        "INSERT INTO users (id, email, name, password_hash, tier) VALUES (?, ?, ?, ?, 'free')",
        (user_id, body.email.lower(), name, password_hash),
    )
    conn.commit()
    conn.close()

    token = create_access_token(user_id, body.email.lower(), "free")
    return AuthOut(token=token, user_id=user_id, email=body.email.lower(), name=name, tier="free")


@router.post("/login", response_model=AuthOut)
def login(body: LoginRequest):
    conn   = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (body.email,))
    row = cursor.fetchone()
    conn.close()

    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    tier  = row["tier"] or "free"
    token = create_access_token(row["id"], row["email"], tier)
    return AuthOut(
        token=token,
        user_id=row["id"],
        email=row["email"],
        name=row["name"] or row["email"].split("@")[0],
        tier=tier,
    )


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, email, tier FROM users WHERE id = ?", (current_user["id"],))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found.")

    return {
        "user_id": current_user["id"],
        "email":   row["email"],
        "name":    row["name"] or row["email"].split("@")[0],
        "tier":    row["tier"] or "free",
    }


@router.post("/upgrade")
def upgrade(current_user: dict = Depends(get_current_user)):
    """
    Mock upgrade endpoint — sets tier to 'premium'.
    In production this would be triggered by a Stripe webhook after payment.
    """
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET tier = 'premium' WHERE id = ?", (current_user["id"],))
    conn.commit()
    conn.close()

    # Issue a new token with updated tier
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE id = ?", (current_user["id"],))
    row    = cursor.fetchone()
    conn.close()

    token = create_access_token(current_user["id"], row["email"], "premium")
    return {"token": token, "tier": "premium", "message": "Upgraded to Premium successfully."}


@router.post("/downgrade")
def downgrade(current_user: dict = Depends(get_current_user)):
    """Dev helper to reset to free tier."""
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET tier = 'free' WHERE id = ?", (current_user["id"],))
    conn.commit()
    conn.close()

    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE id = ?", (current_user["id"],))
    row    = cursor.fetchone()
    conn.close()

    token = create_access_token(current_user["id"], row["email"], "free")
    return {"token": token, "tier": "free"}
