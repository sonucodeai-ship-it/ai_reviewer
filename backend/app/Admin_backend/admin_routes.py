from __future__ import annotations
from datetime import timezone
from fastapi import APIRouter, Header, HTTPException, Request
from mysql.connector import Error
from pydantic import BaseModel, EmailStr, Field
from app.Admin_backend.admin_auth import *
from app.database import get_db

router = APIRouter(prefix="/api/admin", tags=["Admin"])

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class StaffCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role_name: str = Field(min_length=1, max_length=80)

class StaffStatusRequest(BaseModel):
    is_active: bool

class BusinessUpdateRequest(BaseModel):
    business_name: str = Field(min_length=2, max_length=255)
    business_type: str | None = None
    about_business: str | None = None
    year_established: int | None = Field(default=None, ge=1800, le=2100)
    email: EmailStr
    mobile: str | None = None
    user_is_active: bool = True

class DashboardUpdateRequest(BaseModel):
    dashboard_name: str = Field(min_length=1, max_length=150)

class QueryUpdateRequest(BaseModel):
    query_text: str = Field(min_length=1, max_length=1000)

class OptionUpdateRequest(BaseModel):
    option_text: str = Field(min_length=1, max_length=500)

class ReviewUpdateRequest(BaseModel):
    review_text: str = Field(min_length=1)
    submit_status: int = Field(ge=0, le=1)

class WebsiteVersionUpdateRequest(BaseModel):
    html_code: str
    color_theme_1: str | None = None
    color_theme_2: str | None = None


class CoinGrantRequest(BaseModel):
    coins: int = Field(gt=0, le=1000000000)

def audit(cur, admin_id, action, target_type, target_id, description, request=None):
    cur.execute(
        """INSERT INTO admin_audit_log
        (admin_user_id,action,target_type,target_id,description,ip_address,user_agent)
        VALUES(%s,%s,%s,%s,%s,%s,%s)""",
        (
            admin_id, action, target_type, target_id, description,
            request.client.host if request and request.client else None,
            request.headers.get("user-agent") if request else None,
        ),
    )

def admin_json(a):
    return {
        "admin_user_id": int(a["admin_user_id"]),
        "full_name": a["full_name"],
        "email": a["email"],
        "role_id": int(a["role_id"]),
        "role_name": a["role_name"],
        "role_description": a.get("role_description"),
        "is_active": bool(a["is_active"]),
        "last_login_at": a["last_login_at"].isoformat() if a.get("last_login_at") else None,
    }

def business(cur, business_id):
    cur.execute("""SELECT bi.*,u.email_id,u.mobile,u.is_active user_is_active
                   FROM business_info bi JOIN users u ON u.user_id=bi.user_id
                   WHERE bi.business_id=%s LIMIT 1""", (business_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Business not found.")
    return row

# ---------------- AUTH ----------------

@router.post("/auth/login")
def login(p: AdminLoginRequest, request: Request):
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("""SELECT au.*,ar.role_id,ar.role_name,ar.description role_description
                       FROM admin_user au JOIN admin_role ar ON ar.role_id=au.role_id
                       WHERE LOWER(au.email)=LOWER(%s) LIMIT 1""",(p.email,))
        a=cur.fetchone()
        if not a or not verify_admin_password(p.password,a["password_hash"]):
            raise HTTPException(401,"Invalid email or password.")
        if not a["is_active"]:
            raise HTTPException(403,"This admin account is inactive.")
        token,exp=create_admin_access_token(int(a["admin_user_id"]),a["role_name"])
        cur.execute("""INSERT INTO admin_auth_token
                       (admin_user_id,token_hash,expires_at,is_revoked)
                       VALUES(%s,%s,%s,FALSE)""",
                    (a["admin_user_id"],hash_token(token),
                     exp.astimezone(timezone.utc).replace(tzinfo=None)))
        cur.execute("UPDATE admin_user SET last_login_at=UTC_TIMESTAMP() WHERE admin_user_id=%s",
                    (a["admin_user_id"],))
        audit(cur,a["admin_user_id"],"admin.login","admin_user",str(a["admin_user_id"]),
              "Administrator signed in.",request)
        db.commit()
        return {"success":True,"access_token":token,"token_type":"bearer","admin":admin_json(a)}
    except HTTPException:
        db.rollback(); raise
    except Error as e:
        db.rollback(); raise HTTPException(500,"Unable to login as administrator.") from e
    finally:
        cur.close(); db.close()

@router.post("/auth/logout")
def logout(authorization: str=Header(...)):
    a=get_current_admin(authorization)
    revoke_admin_token(extract_raw_admin_token(authorization))
    return {"success":True,"message":"Admin session ended.","admin_user_id":int(a["admin_user_id"])}

@router.get("/auth/me")
def me(authorization: str=Header(...)):
    return {"success":True,"admin":admin_json(get_current_admin(authorization))}

# ---------------- OVERVIEW ----------------

@router.get("/dashboard")
def dashboard(authorization: str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"admin.dashboard.read")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        qs={
            "customers":"SELECT COUNT(*) total FROM users",
            "businesses":"SELECT COUNT(*) total FROM business_info",
            "dashboards":"SELECT COUNT(*) total FROM dashboard",
            "reviews":"SELECT COUNT(*) total FROM review",
            "websites":"SELECT COUNT(*) total FROM website",
            "website_versions":"SELECT COUNT(*) total FROM website_version WHERE html_code<>''",
        }
        counts={}
        for k,q in qs.items():
            cur.execute(q); counts[k]=int(cur.fetchone()["total"] or 0)
        cur.execute("""SELECT audit_id,action,target_type,target_id,description,created_at
                       FROM admin_audit_log ORDER BY created_at DESC LIMIT 12""")
        activity=[dict(x,audit_id=int(x["audit_id"]),
                        created_at=x["created_at"].isoformat() if x["created_at"] else None)
                  for x in cur.fetchall()]
        return {"success":True,"admin":admin_json(a),"counts":counts,"recent_activity":activity}
    finally: cur.close(); db.close()

# ---------------- STAFF ----------------

@router.get("/staff")
def staff(authorization: str=Header(...)):
    a=get_current_admin(authorization); require_super_admin(a)
    require_admin_permission(a,"admin_users.read")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("""SELECT au.admin_user_id,au.full_name,au.email,au.is_active,
                              au.last_login_at,au.created_at,ar.role_name
                       FROM admin_user au JOIN admin_role ar ON ar.role_id=au.role_id
                       ORDER BY au.created_at DESC""")
        return {"success":True,"staff":[
            {"admin_user_id":int(x["admin_user_id"]),"full_name":x["full_name"],
             "email":x["email"],"is_active":bool(x["is_active"]),
             "role_name":x["role_name"],
             "last_login_at":x["last_login_at"].isoformat() if x["last_login_at"] else None}
            for x in cur.fetchall()
        ]}
    finally: cur.close(); db.close()

@router.get("/staff/roles")
def staff_roles(authorization: str=Header(...)):
    a=get_current_admin(authorization); require_super_admin(a)
    require_admin_permission(a,"admin_users.permissions")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("SELECT role_id,role_name,description FROM admin_role WHERE is_active=TRUE ORDER BY role_name")
        return {"success":True,"roles":[dict(x,role_id=int(x["role_id"])) for x in cur.fetchall()]}
    finally: cur.close(); db.close()

@router.post("/staff")
def create_staff(p:StaffCreateRequest,request:Request,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_super_admin(a)
    require_admin_permission(a,"admin_users.create")
    if p.role_name.lower()=="super_admin":
        raise HTTPException(403,"A Super Administrator cannot be created from the staff UI.")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("SELECT admin_user_id FROM admin_user WHERE LOWER(email)=LOWER(%s)",(p.email,))
        if cur.fetchone(): raise HTTPException(409,"An administrator with this email already exists.")
        cur.execute("SELECT role_id,role_name FROM admin_role WHERE role_name=%s AND is_active=TRUE",
                    (p.role_name.lower(),))
        role=cur.fetchone()
        if not role: raise HTTPException(400,"Selected role does not exist.")
        cur.execute("""INSERT INTO admin_user(role_id,full_name,email,password_hash,is_active)
                       VALUES(%s,%s,%s,%s,TRUE)""",
                    (role["role_id"],p.full_name.strip(),p.email.lower(),hash_admin_password(p.password)))
        sid=int(cur.lastrowid)
        audit(cur,a["admin_user_id"],"staff.create","admin_user",str(sid),
              f"Created staff account for {p.email}.",request)
        db.commit()
        return {"success":True,"message":"Staff account created successfully."}
    except HTTPException:
        db.rollback(); raise
    finally:
        cur.close(); db.close()

@router.patch("/staff/{staff_id}/status")
def staff_status(staff_id:int,p:StaffStatusRequest,request:Request,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_super_admin(a)
    require_admin_permission(a,"admin_users.disable")
    if staff_id==int(a["admin_user_id"]): raise HTTPException(400,"You cannot disable yourself.")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("""SELECT au.email,ar.role_name FROM admin_user au
                       JOIN admin_role ar ON ar.role_id=au.role_id
                       WHERE au.admin_user_id=%s""",(staff_id,))
        row=cur.fetchone()
        if not row: raise HTTPException(404,"Staff account not found.")
        if row["role_name"]=="super_admin": raise HTTPException(403,"Super Administrator is protected.")
        cur.execute("UPDATE admin_user SET is_active=%s WHERE admin_user_id=%s",(p.is_active,staff_id))
        audit(cur,a["admin_user_id"],"staff.status","admin_user",str(staff_id),
              f"Changed {row['email']} to {'active' if p.is_active else 'inactive'}.",request)
        db.commit()
        return {"success":True,"message":"Staff status updated."}
    except HTTPException:
        db.rollback(); raise
    finally:
        cur.close(); db.close()



# ---------------- COIN BALANCE ----------------

@router.get("/businesses/{business_id}/coins")
def get_business_coins(
    business_id: int,
    authorization: str = Header(...),
):
    """
    Read the current coin balance for a business.

    This endpoint is restricted to administrators and never exposes
    authentication credentials or unrelated customer data.
    """
    a = get_current_admin(authorization)
    require_admin_permission(a, "businesses.read")

    db = get_db()
    cur = db.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                cb.coin_balance_id,
                cb.user_id,
                cb.business_id,
                cb.coin_balance,
                cb.updates_at
            FROM coin_balance AS cb
            WHERE cb.business_id = %s
            LIMIT 1
            """,
            (business_id,),
        )

        row = cur.fetchone()

        if not row:
            return {
                "success": True,
                "business_id": business_id,
                "coin_balance_id": None,
                "coin_balance": 0,
                "updates_at": None,
            }

        return {
            "success": True,
            "business_id": int(row["business_id"]),
            "coin_balance_id": int(row["coin_balance_id"]),
            "coin_balance": int(row["coin_balance"] or 0),
            "updates_at": (
                row["updates_at"].isoformat()
                if row["updates_at"]
                else None
            ),
        }

    finally:
        cur.close()
        db.close()


@router.post("/businesses/{business_id}/coins/grant")
def grant_business_coins(
    business_id: int,
    p: CoinGrantRequest,
    request: Request,
    authorization: str = Header(...),
):
    """
    Grant coins to a business owner.

    Only Super Admin can grant coins. The operation is transactional:
    the balance and its history record are written together.
    """
    a = get_current_admin(authorization)
    require_super_admin(a)
    require_admin_permission(a, "businesses.update")

    db = get_db()
    cur = db.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                business_id,
                user_id,
                business_name
            FROM business_info
            WHERE business_id = %s
            LIMIT 1
            """,
            (business_id,),
        )

        business_row = cur.fetchone()

        if not business_row:
            raise HTTPException(
                status_code=404,
                detail="Business not found.",
            )

        cur.execute(
            """
            SELECT
                coin_balance_id,
                coin_balance
            FROM coin_balance
            WHERE user_id = %s
              AND business_id = %s
            LIMIT 1
            FOR UPDATE
            """,
            (
                business_row["user_id"],
                business_id,
            ),
        )

        balance_row = cur.fetchone()

        if balance_row:
            coin_balance_id = int(
                balance_row["coin_balance_id"]
            )
            current_balance = int(
                balance_row["coin_balance"] or 0
            )

            new_balance = (
                current_balance + p.coins
            )

            cur.execute(
                """
                UPDATE coin_balance
                SET
                    coin_balance = %s,
                    updates_at = CURRENT_TIMESTAMP
                WHERE coin_balance_id = %s
                """,
                (
                    new_balance,
                    coin_balance_id,
                ),
            )

        else:
            new_balance = p.coins

            cur.execute(
                """
                INSERT INTO coin_balance
                (
                    user_id,
                    business_id,
                    coin_balance
                )
                VALUES
                (
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    business_row["user_id"],
                    business_id,
                    new_balance,
                ),
            )

            coin_balance_id = int(
                cur.lastrowid
            )

        cur.execute(
            """
            SELECT
                COALESCE(
                    MAX(total_coin),
                    0
                ) AS previous_total
            FROM coin_balance_history
            WHERE coin_balance_id = %s
            """,
            (coin_balance_id,),
        )

        history_total = int(
            (
                cur.fetchone()["previous_total"]
                or 0
            )
        )

        total_coin = (
            history_total + p.coins
        )

        cur.execute(
            """
            INSERT INTO coin_balance_history
            (
                coin_balance_id,
                recharged_coin,
                current_coin,
                total_coin
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                coin_balance_id,
                p.coins,
                new_balance,
                total_coin,
            ),
        )

        audit(
            cur,
            a["admin_user_id"],
            "coin.grant",
            "business",
            str(business_id),
            (
                f"Granted {p.coins} coins to "
                f"{business_row['business_name']}. "
                f"New balance: {new_balance}."
            ),
            request,
        )

        db.commit()

        return {
            "success": True,
            "business_id": business_id,
            "coin_balance_id": coin_balance_id,
            "recharged_coin": p.coins,
            "coin_balance": new_balance,
            "total_coin": total_coin,
            "message": "Coins granted successfully.",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to grant coins.",
        ) from error

    finally:
        cur.close()
        db.close()

# ---------------- BUSINESSES ----------------

@router.get("/businesses")
def businesses(authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"businesses.read")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("""SELECT bi.business_id,bi.user_id,bi.business_name,bi.business_type,
                              bi.year_established,bi.updated_at,u.email_id,u.mobile,
                              u.is_active user_is_active,
                              (SELECT COUNT(*) FROM dashboard d WHERE d.business_id=bi.business_id) dashboard_count,
                              (SELECT COUNT(*) FROM website w WHERE w.business_id=bi.business_id) website_count
                       FROM business_info bi JOIN users u ON u.user_id=bi.user_id
                       ORDER BY bi.updated_at DESC LIMIT 500""")
        out=[]
        for x in cur.fetchall():
            out.append({**x,"business_id":int(x["business_id"]),"user_id":int(x["user_id"]),
                        "user_is_active":bool(x["user_is_active"]),
                        "dashboard_count":int(x["dashboard_count"] or 0),
                        "website_count":int(x["website_count"] or 0),
                        "updated_at":x["updated_at"].isoformat() if x["updated_at"] else None})
        return {"success":True,"businesses":out}
    finally: cur.close(); db.close()

@router.get("/businesses/{business_id}")
def business_detail(business_id:int,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"businesses.read")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        b=business(cur,business_id)
        cur.execute("""SELECT dashboard_id,public_url_id,dashboard_name,created_at,updated_at
                       FROM dashboard WHERE business_id=%s ORDER BY updated_at DESC""",(business_id,))
        dashboards=[{**x,"dashboard_id":int(x["dashboard_id"]),
                      "created_at":x["created_at"].isoformat() if x["created_at"] else None,
                      "updated_at":x["updated_at"].isoformat() if x["updated_at"] else None}
                     for x in cur.fetchall()]
        cur.execute("""SELECT w.website_id,w.updated_at,
                      (SELECT COUNT(*) FROM website_version v
                       WHERE v.website_id=w.website_id AND v.html_code<>'') versions
                       FROM website w WHERE w.business_id=%s""",(business_id,))
        websites=[{"website_id":int(x["website_id"]),
                   "versions":int(x["versions"] or 0),
                   "updated_at":x["updated_at"].isoformat() if x["updated_at"] else None}
                  for x in cur.fetchall()]
        cur.execute("""SELECT COUNT(*) total FROM review r JOIN dashboard d
                       ON d.dashboard_id=r.dashboard_id WHERE d.business_id=%s""",(business_id,))
        review_count = int(cur.fetchone()["total"] or 0)
        return {"success":True,"business":{
            "business_id":int(b["business_id"]),"user_id":int(b["user_id"]),
            "business_name":b["business_name"],"business_type":b["business_type"],
            "about_business":b["about_business"],"year_established":b["year_established"],
            "email":b["email_id"],"mobile":b["mobile"],
            "user_is_active":bool(b["user_is_active"]),
            "updated_at":b["updated_at"].isoformat() if b["updated_at"] else None},
            "dashboards":dashboards,"websites":websites,
            "review_count":review_count}
    finally: cur.close(); db.close()

@router.patch("/businesses/{business_id}")
def update_business(business_id:int,p:BusinessUpdateRequest,request:Request,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"businesses.update")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        old=business(cur,business_id)
        cur.execute("""UPDATE business_info SET business_name=%s,business_type=%s,
                       about_business=%s,year_established=%s,updated_at=CURRENT_TIMESTAMP
                       WHERE business_id=%s""",
                    (p.business_name.strip(),p.business_type,p.about_business,p.year_established,business_id))
        cur.execute("""UPDATE users SET email_id=%s,mobile=%s,is_active=%s
                       WHERE user_id=%s""",
                    (p.email.lower(),p.mobile,p.user_is_active,old["user_id"]))
        audit(cur,a["admin_user_id"],"business.update","business",str(business_id),
              "Updated business information.",request)
        db.commit()
        return {"success":True,"message":"Business information updated successfully."}
    except HTTPException:
        db.rollback(); raise
    finally: cur.close(); db.close()

# ---------------- DASHBOARDS / QUESTIONS / OPTIONS ----------------

@router.get("/businesses/{business_id}/dashboards/{dashboard_id}")
def dashboard_detail(business_id:int,dashboard_id:int,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"businesses.read")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("""SELECT dashboard_id,public_url_id,dashboard_name,created_at,updated_at
                       FROM dashboard WHERE dashboard_id=%s AND business_id=%s""",(dashboard_id,business_id))
        d=cur.fetchone()
        if not d: raise HTTPException(404,"Dashboard not found.")
        cur.execute("""SELECT q.query_id,q.query_text,
                       (SELECT COUNT(*) FROM `option` o WHERE o.query_id=q.query_id) option_count
                       FROM query q WHERE q.dashboard_id=%s ORDER BY q.query_id""",(dashboard_id,))
        qs=[{**x,"query_id":int(x["query_id"]),"option_count":int(x["option_count"] or 0)}
            for x in cur.fetchall()]
        cur.execute("""SELECT review_id,review_text,regenerate_status,submit_status
                       FROM review WHERE dashboard_id=%s ORDER BY review_id DESC LIMIT 200""",(dashboard_id,))
        reviews=[{**x,"review_id":int(x["review_id"]),
                   "submit_status":int(x["submit_status"] or 0)}
                  for x in cur.fetchall()]
        return {"success":True,"dashboard":{
            **d,"dashboard_id":int(d["dashboard_id"]),
            "created_at":d["created_at"].isoformat() if d["created_at"] else None,
            "updated_at":d["updated_at"].isoformat() if d["updated_at"] else None},
            "queries":qs,"reviews":reviews}
    finally: cur.close(); db.close()

@router.patch("/businesses/{business_id}/dashboards/{dashboard_id}")
def update_dashboard(business_id:int,dashboard_id:int,p:DashboardUpdateRequest,request:Request,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"businesses.update")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("SELECT dashboard_id FROM dashboard WHERE dashboard_id=%s AND business_id=%s",(dashboard_id,business_id))
        if not cur.fetchone(): raise HTTPException(404,"Dashboard not found.")
        cur.execute("UPDATE dashboard SET dashboard_name=%s,updated_at=CURRENT_TIMESTAMP WHERE dashboard_id=%s",
                    (p.dashboard_name.strip(),dashboard_id))
        audit(cur,a["admin_user_id"],"dashboard.update","dashboard",str(dashboard_id),
              "Updated dashboard name.",request)
        db.commit(); return {"success":True,"message":"Dashboard updated successfully."}
    except HTTPException:
        db.rollback(); raise
    finally: cur.close(); db.close()

@router.get("/businesses/{business_id}/queries/{query_id}")
def query_detail(business_id:int,query_id:int,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"businesses.read")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("""SELECT q.query_id,q.query_text,q.dashboard_id FROM query q
                       JOIN dashboard d ON d.dashboard_id=q.dashboard_id
                       WHERE q.query_id=%s AND d.business_id=%s""",(query_id,business_id))
        q=cur.fetchone()
        if not q: raise HTTPException(404,"Question not found.")
        cur.execute("SELECT option_id,option_text FROM `option` WHERE query_id=%s ORDER BY option_id",(query_id,))
        return {"success":True,"query":{**q,"query_id":int(q["query_id"]),"dashboard_id":int(q["dashboard_id"])},
                "options":[{"option_id":int(x["option_id"]),"option_text":x["option_text"]} for x in cur.fetchall()]}
    finally: cur.close(); db.close()

@router.patch("/businesses/{business_id}/queries/{query_id}")
def update_query(business_id:int,query_id:int,p:QueryUpdateRequest,request:Request,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"businesses.update")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("""SELECT q.query_id FROM query q JOIN dashboard d ON d.dashboard_id=q.dashboard_id
                       WHERE q.query_id=%s AND d.business_id=%s""",(query_id,business_id))
        if not cur.fetchone(): raise HTTPException(404,"Question not found.")
        cur.execute("UPDATE query SET query_text=%s,updated_at=CURRENT_TIMESTAMP WHERE query_id=%s",
                    (p.query_text.strip(),query_id))
        audit(cur,a["admin_user_id"],"query.update","query",str(query_id),"Updated customer question.",request)
        db.commit(); return {"success":True,"message":"Question updated successfully."}
    except HTTPException:
        db.rollback(); raise
    finally: cur.close(); db.close()

@router.patch("/businesses/{business_id}/options/{option_id}")
def update_option(business_id:int,option_id:int,p:OptionUpdateRequest,request:Request,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"businesses.update")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("""SELECT o.option_id FROM `option` o JOIN query q ON q.query_id=o.query_id
                       JOIN dashboard d ON d.dashboard_id=q.dashboard_id
                       WHERE o.option_id=%s AND d.business_id=%s""",(option_id,business_id))
        if not cur.fetchone(): raise HTTPException(404,"Option not found.")
        cur.execute("UPDATE `option` SET option_text=%s,updated_at=CURRENT_TIMESTAMP WHERE option_id=%s",
                    (p.option_text.strip(),option_id))
        audit(cur,a["admin_user_id"],"option.update","option",str(option_id),"Updated dashboard option.",request)
        db.commit(); return {"success":True,"message":"Option updated successfully."}
    except HTTPException:
        db.rollback(); raise
    finally: cur.close(); db.close()

# ---------------- REVIEWS ----------------

@router.patch("/businesses/{business_id}/reviews/{review_id}")
def update_review(business_id:int,review_id:int,p:ReviewUpdateRequest,request:Request,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"reviews.read")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("""SELECT r.review_id FROM review r JOIN dashboard d ON d.dashboard_id=r.dashboard_id
                       WHERE r.review_id=%s AND d.business_id=%s""",(review_id,business_id))
        if not cur.fetchone(): raise HTTPException(404,"Review not found.")
        cur.execute("UPDATE review SET review_text=%s,submit_status=%s WHERE review_id=%s",
                    (p.review_text.strip(),p.submit_status,review_id))
        audit(cur,a["admin_user_id"],"review.update","review",str(review_id),"Updated generated review.",request)
        db.commit(); return {"success":True,"message":"Review updated successfully."}
    except HTTPException:
        db.rollback(); raise
    finally: cur.close(); db.close()

# ---------------- WEBSITES ----------------

@router.get("/businesses/{business_id}/websites")
def websites(business_id:int,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"websites.read")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        business(cur,business_id)
        cur.execute("""SELECT v.website_version_id,v.website_id,v.version_number,v.public_url_id,
                              v.color_theme_1,v.color_theme_2,v.created_at
                       FROM website_version v JOIN website w ON w.website_id=v.website_id
                       WHERE w.business_id=%s AND v.html_code<>'' ORDER BY v.version_number DESC""",(business_id,))
        return {"success":True,"versions":[
            {**x,"website_version_id":int(x["website_version_id"]),"website_id":int(x["website_id"]),
             "version_number":int(x["version_number"]),
             "created_at":x["created_at"].isoformat() if x["created_at"] else None}
            for x in cur.fetchall()
        ]}
    finally: cur.close(); db.close()

@router.get("/businesses/{business_id}/websites/versions/{version_id}")
def website_version(business_id:int,version_id:int,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"websites.read")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("""SELECT v.* FROM website_version v JOIN website w ON w.website_id=v.website_id
                       WHERE v.website_version_id=%s AND w.business_id=%s""",(version_id,business_id))
        v=cur.fetchone()
        if not v: raise HTTPException(404,"Website version not found.")
        return {"success":True,"version":{
            "website_version_id":int(v["website_version_id"]),"website_id":int(v["website_id"]),
            "version_number":int(v["version_number"]),"public_url_id":v["public_url_id"],
            "html_code":v["html_code"],"color_theme_1":v["color_theme_1"],
            "color_theme_2":v["color_theme_2"],"is_active":bool(v["is_active"])
        }}
    finally: cur.close(); db.close()

@router.patch("/businesses/{business_id}/websites/versions/{version_id}")
def update_website_version(
    business_id:int,
    version_id:int,
    p:WebsiteVersionUpdateRequest,
    request:Request,
    authorization:str=Header(...)
):
    a=get_current_admin(authorization)
    require_admin_permission(a,"businesses.update")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("""SELECT v.website_id,v.version_number
                       FROM website_version v JOIN website w ON w.website_id=v.website_id
                       WHERE v.website_version_id=%s AND w.business_id=%s""",
                    (version_id,business_id))
        v=cur.fetchone()
        if not v:
            raise HTTPException(404,"Website version not found.")

        # Website versions are owner-owned content/history records.
        # There is intentionally no admin-level published/active concept.
        cur.execute("""UPDATE website_version
                       SET html_code=%s,color_theme_1=%s,color_theme_2=%s
                       WHERE website_version_id=%s""",
                    (p.html_code,p.color_theme_1,p.color_theme_2,version_id))
        cur.execute("UPDATE website SET updated_at=CURRENT_TIMESTAMP WHERE website_id=%s",
                    (v["website_id"],))
        audit(cur,a["admin_user_id"],"website_version.update","website_version",
              str(version_id),f"Updated website V{v['version_number']}.",request)
        db.commit()
        return {"success":True,"message":"Website version updated successfully."}
    except HTTPException:
        db.rollback(); raise
    finally:
        cur.close(); db.close()

# ---------------- GOOGLE / AUDIT ----------------

@router.get("/businesses/{business_id}/google")
def google(business_id:int,authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"google.read")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        business(cur,business_id)
        cur.execute("""SELECT connection_id,google_account_name,google_account_id,
                       google_location_name,google_location_id,google_location_title,
                       connection_status,access_token_expires_at,created_at,updated_at
                       FROM google_business_connection WHERE business_id=%s LIMIT 1""",(business_id,))
        x=cur.fetchone()
        if x:
            x["connection_id"]=int(x["connection_id"])
            for k in ("access_token_expires_at","created_at","updated_at"):
                if x.get(k): x[k]=x[k].isoformat()
        return {"success":True,"google":x}
    finally: cur.close(); db.close()

@router.get("/audit-logs")
def audit_logs(authorization:str=Header(...)):
    a=get_current_admin(authorization); require_admin_permission(a,"audit_logs.read")
    db=get_db(); cur=db.cursor(dictionary=True)
    try:
        cur.execute("""SELECT al.audit_id,al.action,al.target_type,al.target_id,al.description,
                       al.ip_address,al.user_agent,al.created_at,au.full_name admin_name,au.email admin_email
                       FROM admin_audit_log al LEFT JOIN admin_user au ON au.admin_user_id=al.admin_user_id
                       ORDER BY al.created_at DESC LIMIT 500""")
        return {"success":True,"audit_logs":[
            {**x,"audit_id":int(x["audit_id"]),
             "created_at":x["created_at"].isoformat() if x["created_at"] else None}
            for x in cur.fetchall()
        ]}
    finally: cur.close(); db.close()
