"""Backend ООО «Европа-Тур»: FastAPI + SQLModel + Redis."""
import os
import json
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from sqlmodel import SQLModel, Field, Session, create_engine, select, Relationship
import bcrypt
from jose import JWTError, jwt
import redis

# ====================== Конфиг ======================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./europa_tour.db")
# Render и некоторые хостинги отдают URL вида postgres://...
# SQLAlchemy ожидает postgresql:// — приводим к нужному виду.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRES = 60 * 24  # минут

engine = create_engine(DATABASE_URL, echo=False)

# Встроенная функция SQLite lower() не понимает кириллицу и переводит
# в нижний регистр только латиницу. Регистрируем свою юникод-версию,
# чтобы поиск по названию отеля/города/страны работал без учёта регистра.
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _register_unicode_lower(dbapi_conn, _):
        dbapi_conn.create_function(
            "lower", 1, lambda s: s.lower() if isinstance(s, str) else s
        )

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_pwd(p: str) -> str:
    return bcrypt.hashpw(p.encode('utf-8')[:72], bcrypt.gensalt()).decode('utf-8')

def verify_pwd(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode('utf-8')[:72], h.encode('utf-8'))
    except Exception:
        return False
try:
    cache = redis.from_url(REDIS_URL, decode_responses=True)
    cache.ping()
except Exception:
    cache = None

def cache_clear(prefix: str = "tours:"):
    """Сбросить кеш каталога после изменений."""
    if not cache:
        return
    try:
        for key in cache.scan_iter(f"{prefix}*"):
            cache.delete(key)
    except Exception:
        pass

# ====================== Модели БД ======================
class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    role: str = "client"
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Country(SQLModel, table=True):
    __tablename__ = "countries"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    code: str = Field(unique=True)
    visa_required: bool = False

class Hotel(SQLModel, table=True):
    __tablename__ = "hotels"
    id: Optional[int] = Field(default=None, primary_key=True)
    country_id: int = Field(foreign_key="countries.id")
    name: str
    city: str
    star_rating: int = 4

class Tour(SQLModel, table=True):
    __tablename__ = "tours"
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    country_id: int = Field(foreign_key="countries.id")
    hotel_id: int = Field(foreign_key="hotels.id")
    nights_min: int = 7
    nights_max: int = 14
    board_type: str = "AI"  # RO/BB/HB/FB/AI
    price_per_night: Decimal = Field(max_digits=10, decimal_places=2)
    description: str = ""
    image_url: str = ""
    is_active: bool = True

class Booking(SQLModel, table=True):
    __tablename__ = "bookings"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tour_id: int = Field(foreign_key="tours.id", index=True)
    check_in: date
    nights: int
    adults: int = 1
    children: int = 0
    total_price: Decimal = Field(max_digits=12, decimal_places=2)
    status: str = "created"  # created/paid/confirmed/cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Favorite(SQLModel, table=True):
    __tablename__ = "favorites"
    user_id: int = Field(foreign_key="users.id", primary_key=True)
    tour_id: int = Field(foreign_key="tours.id", primary_key=True)
    added_at: datetime = Field(default_factory=datetime.utcnow)


# ====================== Pydantic-схемы ======================
class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    first_name: str = ""
    last_name: str = ""
    phone: str = ""

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class TourOut(BaseModel):
    id: int
    title: str
    country: str
    city: str
    hotel: str
    stars: int
    nights_min: int
    nights_max: int
    board_type: str
    price_per_night: float
    description: str
    image_url: str

class BookingCreate(BaseModel):
    tour_id: int
    check_in: date
    nights: int
    adults: int = 1
    children: int = 0

class BookingOut(BaseModel):
    id: int
    tour_id: int
    tour_title: str
    check_in: date
    nights: int
    adults: int
    children: int
    total_price: float
    status: str
    created_at: datetime


# ====================== Хелперы ======================
def get_db():
    with Session(engine) as s:
        yield s

def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    err = HTTPException(401, "Невалидный токен")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise err
    user = db.get(User, user_id)
    if not user:
        raise err
    return user

def user_public(user: User) -> dict:
    return {
        "id": user.id, "email": user.email,
        "first_name": user.first_name, "last_name": user.last_name,
        "phone": user.phone,
    }


# ====================== Жизненный цикл ======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    # Автонаполнение БД при первом запуске — нужно для хостинга (Render и т.п.),
    # где нет доступа к консоли, чтобы запустить seed.py вручную.
    if os.getenv("AUTO_SEED", "1") == "1":
        try:
            from seed import seed
            print("[seed]", seed())
        except Exception as e:
            print("[seed] пропущено:", e)
    yield

app = FastAPI(title="ООО «Европа-Тур»", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================== Endpoints ======================
@app.get("/api")
def api_root():
    """Статус API. Корень / отдаёт сам сайт (см. раздачу статики ниже)."""
    return {"app": "Европа-Тур", "status": "ok", "redis": bool(cache)}

# ---- Аутентификация ----
@app.post("/api/auth/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.exec(select(User).where(User.email == data.email)).first():
        raise HTTPException(409, "Пользователь с таким email уже зарегистрирован")
    user = User(
        email=data.email,
        password_hash=hash_pwd(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
    )
    db.add(user); db.commit(); db.refresh(user)
    # Регистрация сразу выполняет вход — без подтверждения email.
    return TokenOut(
        access_token=create_token(user.id),
        user=user_public(user),
    )

@app.post("/api/auth/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.exec(select(User).where(User.email == data.email)).first()
    if not user or not verify_pwd(data.password, user.password_hash):
        raise HTTPException(401, "Неверный email или пароль")
    return TokenOut(
        access_token=create_token(user.id),
        user=user_public(user),
    )

@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return user_public(user)

# ---- Профиль ----
@app.patch("/api/auth/me")
def update_profile(data: ProfileUpdate, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    if data.first_name is not None:
        user.first_name = data.first_name.strip()
    if data.last_name is not None:
        user.last_name = data.last_name.strip()
    if data.phone is not None:
        user.phone = data.phone.strip()
    db.add(user); db.commit(); db.refresh(user)
    return user_public(user)

@app.post("/api/auth/password")
def change_password(data: PasswordChange, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    if not verify_pwd(data.old_password, user.password_hash):
        raise HTTPException(400, "Текущий пароль указан неверно")
    if len(data.new_password) < 6:
        raise HTTPException(400, "Новый пароль должен быть не короче 6 символов")
    user.password_hash = hash_pwd(data.new_password)
    db.add(user); db.commit()
    return {"ok": True, "message": "Пароль изменён"}


# ---- Каталог туров ----
@app.get("/api/tours")
def list_tours(
    country_id: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    board_type: Optional[str] = None,
    stars: Optional[int] = None,
    q: Optional[str] = None,
    sort: Optional[str] = None,  # price_asc / price_desc / stars_desc
    page: int = Query(1, ge=1),
    size: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    # Кеширование результата
    cache_key = f"tours:{country_id}:{min_price}:{max_price}:{board_type}:{stars}:{q}:{sort}:{page}:{size}"
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return json.loads(cached)

    stmt = select(Tour, Hotel, Country).join(Hotel, Tour.hotel_id == Hotel.id) \
        .join(Country, Tour.country_id == Country.id).where(Tour.is_active == True)
    if country_id:
        stmt = stmt.where(Tour.country_id == country_id)
    if min_price is not None:
        stmt = stmt.where(Tour.price_per_night >= min_price)
    if max_price is not None:
        stmt = stmt.where(Tour.price_per_night <= max_price)
    if board_type:
        stmt = stmt.where(Tour.board_type == board_type)
    if stars:
        stmt = stmt.where(Hotel.star_rating == stars)
    if q:
        # Поиск без учёта регистра по названию тура, отелю, городу и стране.
        like = f"%{q.lower()}%"
        from sqlalchemy import func
        stmt = stmt.where(
            (func.lower(Tour.title).like(like)) |
            (func.lower(Hotel.name).like(like)) |
            (func.lower(Hotel.city).like(like)) |
            (func.lower(Country.name).like(like))
        )
    # Сортировка
    if sort == "price_asc":
        stmt = stmt.order_by(Tour.price_per_night.asc())
    elif sort == "price_desc":
        stmt = stmt.order_by(Tour.price_per_night.desc())
    elif sort == "stars_desc":
        stmt = stmt.order_by(Hotel.star_rating.desc())

    rows = db.exec(stmt.offset((page-1)*size).limit(size)).all()
    items = [
        TourOut(
            id=t.id, title=t.title, country=c.name, city=h.city, hotel=h.name,
            stars=h.star_rating, nights_min=t.nights_min, nights_max=t.nights_max,
            board_type=t.board_type, price_per_night=float(t.price_per_night),
            description=t.description, image_url=t.image_url,
        ).model_dump() for t, h, c in rows
    ]
    result = {"items": items, "page": page, "size": size}
    if cache:
        cache.setex(cache_key, 300, json.dumps(result, default=str))
    return result

@app.get("/api/tours/{tour_id}", response_model=TourOut)
def get_tour(tour_id: int, db: Session = Depends(get_db)):
    row = db.exec(
        select(Tour, Hotel, Country).join(Hotel, Tour.hotel_id == Hotel.id)
            .join(Country, Tour.country_id == Country.id).where(Tour.id == tour_id)
    ).first()
    if not row:
        raise HTTPException(404, "Тур не найден")
    t, h, c = row
    return TourOut(
        id=t.id, title=t.title, country=c.name, city=h.city, hotel=h.name,
        stars=h.star_rating, nights_min=t.nights_min, nights_max=t.nights_max,
        board_type=t.board_type, price_per_night=float(t.price_per_night),
        description=t.description, image_url=t.image_url,
    )

@app.get("/api/countries")
def list_countries(db: Session = Depends(get_db)):
    countries = db.exec(select(Country)).all()
    return [{"id": c.id, "name": c.name, "code": c.code} for c in countries]


# ---- Бронирования ----
@app.post("/api/bookings", response_model=BookingOut, status_code=201)
def create_booking(data: BookingCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    tour = db.get(Tour, data.tour_id)
    if not tour:
        raise HTTPException(404, "Тур не найден")
    if data.nights < tour.nights_min or data.nights > tour.nights_max:
        raise HTTPException(400, f"Количество ночей для этого тура: от {tour.nights_min} до {tour.nights_max}")
    base = tour.price_per_night * data.nights
    total = base * (Decimal(data.adults) + Decimal("0.5") * data.children)
    total = total.quantize(Decimal("0.01"))
    b = Booking(
        user_id=user.id, tour_id=tour.id, check_in=data.check_in,
        nights=data.nights, adults=data.adults, children=data.children,
        total_price=total,
    )
    db.add(b); db.commit(); db.refresh(b)
    return BookingOut(
        id=b.id, tour_id=b.tour_id, tour_title=tour.title,
        check_in=b.check_in, nights=b.nights, adults=b.adults, children=b.children,
        total_price=float(b.total_price), status=b.status, created_at=b.created_at,
    )

@app.get("/api/bookings/me", response_model=List[BookingOut])
def my_bookings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.exec(
        select(Booking, Tour).join(Tour, Booking.tour_id == Tour.id)
            .where(Booking.user_id == user.id).order_by(Booking.created_at.desc())
    ).all()
    return [
        BookingOut(
            id=b.id, tour_id=b.tour_id, tour_title=t.title,
            check_in=b.check_in, nights=b.nights, adults=b.adults, children=b.children,
            total_price=float(b.total_price), status=b.status, created_at=b.created_at,
        ) for b, t in rows
    ]

def _get_own_booking(booking_id: int, user: User, db: Session) -> Booking:
    b = db.get(Booking, booking_id)
    if not b or b.user_id != user.id:
        raise HTTPException(404, "Бронирование не найдено")
    return b

@app.post("/api/bookings/{booking_id}/pay")
def pay_booking(booking_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Имитация оплаты. В реальной системе здесь интеграция с платёжным шлюзом."""
    b = _get_own_booking(booking_id, user, db)
    if b.status == "cancelled":
        raise HTTPException(400, "Отменённое бронирование оплатить нельзя")
    if b.status in ("paid", "confirmed"):
        raise HTTPException(400, "Бронирование уже оплачено")
    b.status = "paid"
    db.add(b); db.commit()
    return {"ok": True, "status": b.status, "message": "Оплата прошла успешно"}

@app.post("/api/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    b = _get_own_booking(booking_id, user, db)
    if b.status == "cancelled":
        return {"ok": True, "status": b.status}
    if b.status == "confirmed":
        raise HTTPException(400, "Подтверждённый тур нельзя отменить онлайн — обратитесь к менеджеру")
    b.status = "cancelled"
    db.add(b); db.commit()
    return {"ok": True, "status": b.status, "message": "Бронирование отменено"}


# ---- Избранное ----
@app.post("/api/favorites/{tour_id}")
def add_favorite(tour_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not db.get(Tour, tour_id):
        raise HTTPException(404, "Тур не найден")
    if db.get(Favorite, (user.id, tour_id)):
        return {"ok": True}
    db.add(Favorite(user_id=user.id, tour_id=tour_id)); db.commit()
    return {"ok": True}

@app.delete("/api/favorites/{tour_id}")
def remove_favorite(tour_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    fav = db.get(Favorite, (user.id, tour_id))
    if fav:
        db.delete(fav); db.commit()
    return {"ok": True}

@app.get("/api/favorites")
def list_favorites(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.exec(
        select(Tour, Hotel, Country, Favorite)
            .join(Hotel, Tour.hotel_id == Hotel.id)
            .join(Country, Tour.country_id == Country.id)
            .join(Favorite, Favorite.tour_id == Tour.id)
            .where(Favorite.user_id == user.id)
            .order_by(Favorite.added_at.desc())
    ).all()
    return [
        TourOut(
            id=t.id, title=t.title, country=c.name, city=h.city, hotel=h.name,
            stars=h.star_rating, nights_min=t.nights_min, nights_max=t.nights_max,
            board_type=t.board_type, price_per_night=float(t.price_per_night),
            description=t.description, image_url=t.image_url,
        ).model_dump() for t, h, c, f in rows
    ]

@app.get("/api/favorites/ids")
def favorite_ids(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Список id избранных туров — для подсветки сердечек в каталоге."""
    rows = db.exec(select(Favorite.tour_id).where(Favorite.user_id == user.id)).all()
    return {"ids": list(rows)}

# ====================== Раздача фронтенда ======================
# Backend сам отдаёт статические файлы сайта (index.html, styles.css, app.js,
# favicon.svg). Это позволяет хостить сайт и API одним сервисом — без CORS
# и без отдельной настройки адреса API. Папка frontend лежит рядом с backend.
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

if os.path.isdir(FRONTEND_DIR):
    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    # Все остальные файлы (css, js, favicon и т.д.) монтируются на /.
    # Монтирование идёт ПОСЛЕ объявления всех /api-роутов, поэтому API не перекрывается.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")

