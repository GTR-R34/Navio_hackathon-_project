from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import bcrypt

from database import init_db, get_db, get_user_by_mobile, create_user, get_user_by_id

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Creates database tables on startup
init_db()


# ─── HOME PAGE ────────────────────────────────────────────────────
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


# ─── EMERGENCY PAGE (no login required) ───────────────────────────
@app.get("/emergency")
def emergency(request: Request):
    return templates.TemplateResponse("emergency.html", {"request": request})


# ─── SIGNUP ───────────────────────────────────────────────────────
@app.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup")
def signup(
    request: Request,
    name: str = Form(...),
    age: int = Form(...),
    gender: str = Form(...),
    mobile: str = Form(...),
    password: str = Form(...),
    category: str = Form(...),          # "differently_abled" or "senior"
    disability_type: str = Form(None),  # only for differently_abled
    emergency_contacts: str = Form(None),
    db: Session = Depends(get_db)
):
    # Validate category
    if category not in ("disabled", "differently_abled", "senior"):
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "Please select a valid category."
        })

    # Check if mobile already registered
    existing = get_user_by_mobile(db, mobile)
    if existing:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "Mobile number already registered. Please login."
        })

    # Hash the password
    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # Create user
    user = create_user(
        db=db,
        name=name,
        age=age,
        gender=gender,
        mobile=mobile,
        hashed_password=hashed_pw,
        category=category,
        disability_type=disability_type,
        emergency_contacts=emergency_contacts
    )

    # Redirect directly to their category page — no generic dashboard
    if user.category in ("disabled", "differently_abled"):
        return RedirectResponse(url=f"/disabled/{user.id}", status_code=302)
    else:
        return RedirectResponse(url=f"/senior/{user.id}", status_code=302)


# ─── LOGIN ────────────────────────────────────────────────────────
@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(
    request: Request,
    mobile: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Find user
    user = get_user_by_mobile(db, mobile)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Mobile number not found. Please sign up."
        })

    # Check password
    if not bcrypt.checkpw(password.encode("utf-8"), user.password.encode("utf-8")):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Incorrect password. Please try again."
        })

    # Redirect directly to their category page — no generic dashboard
    if user.category in ("disabled", "differently_abled"):
        return RedirectResponse(url=f"/disabled/{user.id}", status_code=302)
    else:
        return RedirectResponse(url=f"/senior/{user.id}", status_code=302)


# ─── LOGOUT ───────────────────────────────────────────────────────
@app.get("/logout")
def logout():
    return RedirectResponse(url="/", status_code=302)


# ─── DASHBOARD ────────────────────────────────────────────────────
@app.get("/dashboard/{user_id}")
def dashboard(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Parse emergency contacts
    emergency_contacts = []
    if user.emergency_contacts:
        for contact in user.emergency_contacts.split(","):
            parts = contact.split(":")
            if len(parts) == 2:
                emergency_contacts.append({"name": parts[0], "number": parts[1]})

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "emergency_contacts": emergency_contacts
    })


# ─── CATEGORY PAGES ───────────────────────────────────────────────
@app.get("/disabled/{user_id}")
def disabled(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse("disabled.html", {
        "request": request,
        "user": user,
        "disability_type": user.disability_type
    })

@app.get("/api/nearby")
def nearby(lat: float, lng: float, filter: str = "all"):
    import httpx
    import math

    r = 2000  # 2km radius

    # Build queries directly with f-strings — no .format() risk
    queries_map = {
        "elevator": f"""
            node["highway"="elevator"](around:{r},{lat},{lng});
            node["amenity"="elevator"](around:{r},{lat},{lng});
            node["building"="elevator"](around:{r},{lat},{lng});
            node["amenity"="hospital"](around:{r},{lat},{lng});
            way["amenity"="hospital"](around:{r},{lat},{lng});
            node["amenity"="clinic"](around:{r},{lat},{lng});
            node["amenity"="mall"](around:{r},{lat},{lng});
            way["shop"="mall"](around:{r},{lat},{lng});
        """,
        "rest": f"""
            node["amenity"="bench"](around:{r},{lat},{lng});
            node["leisure"="park"](around:{r},{lat},{lng});
            way["leisure"="park"](around:{r},{lat},{lng});
            node["amenity"="shelter"](around:{r},{lat},{lng});
            node["tourism"="picnic_site"](around:{r},{lat},{lng});
            node["amenity"="cafe"](around:{r},{lat},{lng});
            node["amenity"="restaurant"](around:{r},{lat},{lng});
        """,
        "washroom": f"""
            node["amenity"="toilets"](around:{r},{lat},{lng});
            way["amenity"="toilets"](around:{r},{lat},{lng});
            node["amenity"="hospital"](around:{r},{lat},{lng});
            way["amenity"="hospital"](around:{r},{lat},{lng});
            node["amenity"="clinic"](around:{r},{lat},{lng});
            node["amenity"="pharmacy"](around:{r},{lat},{lng});
            node["shop"="mall"](around:{r},{lat},{lng});
            way["shop"="mall"](around:{r},{lat},{lng});
            node["amenity"="cafe"](around:{r},{lat},{lng});
            node["amenity"="restaurant"](around:{r},{lat},{lng});
        """,
        "hospital": f"""
            node["amenity"="hospital"](around:{r},{lat},{lng});
            way["amenity"="hospital"](around:{r},{lat},{lng});
            node["amenity"="clinic"](around:{r},{lat},{lng});
            node["amenity"="pharmacy"](around:{r},{lat},{lng});
            node["amenity"="doctors"](around:{r},{lat},{lng});
            node["amenity"="health_centre"](around:{r},{lat},{lng});
        """,
        "all": f"""
            node["amenity"~"hospital|clinic|pharmacy|toilets|bench|shelter|cafe|restaurant|doctors"](around:{r},{lat},{lng});
            way["amenity"~"hospital|clinic"](around:{r},{lat},{lng});
            node["leisure"="park"](around:{r},{lat},{lng});
            way["leisure"="park"](around:{r},{lat},{lng});
            node["highway"="elevator"](around:{r},{lat},{lng});
        """,
    }

    inner = queries_map.get(filter, queries_map["all"])
    query = f"[out:json][timeout:20];\n(\n{inner}\n);\nout center 30;"

    def haversine(elat, elng):
        R = 6371000
        dlat = math.radians(elat - lat)
        dlon = math.radians(elng - lng)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(elat)) * math.sin(dlon/2)**2
        return int(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

    def friendly_name(tags):
        name = tags.get("name")
        if name:
            return name.title()
        label_map = {
            "bench":         "Seating / Rest Spot",
            "toilets":       "Public Washroom",
            "shelter":       "Shelter / Rest Area",
            "hospital":      "Hospital (Has Washrooms)",
            "clinic":        "Clinic (Has Washrooms)",
            "pharmacy":      "Pharmacy",
            "doctors":       "Doctor",
            "health_centre": "Health Centre",
            "park":          "Park",
            "elevator":      "Elevator",
            "cafe":          "Café (Has Washrooms)",
            "restaurant":    "Restaurant (Has Washrooms)",
            "mall":          "Shopping Mall (Has Washrooms)",
        }
        for key in [tags.get("amenity",""), tags.get("highway",""), tags.get("leisure",""), tags.get("shop","")]:
            if key in label_map:
                return label_map[key]
        return "Accessible Place"

    try:
        resp = httpx.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=20
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])

        places = []
        seen = set()

        for el in elements:
            tags = el.get("tags", {})

            if el["type"] == "node":
                elat, elng = el["lat"], el["lon"]
            else:
                center = el.get("center", {})
                if not center:
                    continue
                elat, elng = center.get("lat", lat), center.get("lon", lng)

            coord_key = (round(elat, 4), round(elng, 4))
            if coord_key in seen:
                continue
            seen.add(coord_key)

            dist = haversine(elat, elng)

            places.append({
                "name": friendly_name(tags),
                "address": tags.get("addr:street") or tags.get("addr:full") or tags.get("addr:place") or "",
                "lat": elat,
                "lng": elng,
                "distance_m": dist,
                "types": [t for t in [
                    tags.get("amenity",""),
                    tags.get("highway",""),
                    tags.get("leisure",""),
                    tags.get("shop",""),
                ] if t],
                "wheelchair": tags.get("wheelchair", ""),
            })

        places.sort(key=lambda p: p["distance_m"])
        return {"places": places[:15]}

    except Exception as e:
        return {"places": [], "error": str(e)}



@app.get("/senior/{user_id}")
def senior(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse("senior.html", {
        "request": request,
        "user": user
    })