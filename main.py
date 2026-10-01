from pathlib import Path
from datetime import date, datetime, timedelta
import calendar
import os
import hashlib
import hmac
import secrets
import sqlite3

from fastapi import Depends, FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from database import Base, engine, get_db, DATABASE_PATH
from models import User, CatalogImage, Event, EventAttendance, ValuableItem, ClanSetting, EventSetting

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_DIR = BASE_DIR / "static" / "game_catalog"
CATALOG_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_FIELDS = {
    "character_card": "character_card",
    "weapon": "weapon",
    "gloves": "gloves",
    "cloak": "cloak",
    "earring_1": "earring_1",
    "earring_2": "earring_2",
    "necklace": "necklace",
    "belt": "belt",
    "bracelet_1": "bracelet_1",
    "bracelet_2": "bracelet_2",
    "ring_1": "ring_1",
    "ring_2": "ring_2",
    "totem": "totem",
    "seal": "seal",
    "hat": "hat",
    "body": "body",
    "pants": "pants",
    "boots": "boots",
    "symbol": "symbol",
    "artifact": "artifact",
}

# Какую категорию каталога показывать для каждого слота.
SLOT_CATEGORIES = {
    "character_card": "character",
    "weapon": "weapon",
    "gloves": "gloves",
    "cloak": "cloak",
    "earring_1": "earring",
    "earring_2": "earring",
    "necklace": "necklace",
    "belt": "belt",
    "bracelet_1": "bracelet",
    "bracelet_2": "bracelet",
    "ring_1": "ring",
    "ring_2": "ring",
    "totem": "totem",
    "seal": "seal",
    "hat": "hat",
    "body": "body",
    "pants": "pants",
    "boots": "boots",
    "symbol": "symbol",
    "artifact": "artifact",
}

CLASS_OPTIONS = {
    "vanguard_fighter": "Боец Авангарда",
    "berserk": "Берсерк",
    "destroyer": "Разрушитель",
    "night_tracker": "Ночной следопыт",
    "elemental_master": "Мастер стихий",
    "sky_caster": "Небесный заклинатель",
    "assassin": "Убийца",
    "deathdealer": "Смертоносец",
    "shooter": "Стрелок",
    "warlord": "Военачальник",
}
DEFAULT_CLASS_KEY = "vanguard_fighter"
VALID_TIERS = ("T1", "T2", "T3")

# Иерархия должностей клана. Чем меньше число, тем выше должность.
ROLE_OPTIONS = {
    "chief": "Глава",
    "officer": "Офицер",
    "sergeant": "Сержант",
    "fighter": "Боец",
}
ROLE_PRIORITY = {"chief": 0, "officer": 1, "sergeant": 2, "fighter": 3}
ROLE_CSS_CLASSES = {
    "chief": "role-chief",
    "officer": "role-officer",
    "sergeant": "role-sergeant",
    "fighter": "role-fighter",
}
DEFAULT_ROLE = "fighter"
ADMIN_USERNAME = "Admin"
ADMIN_INITIAL_PASSWORD = os.getenv("ADMIN_INITIAL_PASSWORD", "")

EVENT_TYPES = {
    "evening_prime": "Вечерний прайм",
    "guild_dungeon": "Данж Гильдии",
}
ATTENDANCE_MODES = {
    "self": "Игроки отмечают только себя",
    "admin": "Отмечать может только системный аккаунт",
}
MONTH_NAMES_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
WEEKDAY_NAMES_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

# Каталог снаряжения разделён по классу и уровню экипировки.
# Пример: static/game_catalog/weapon/vanguard_fighter/T1/sword.png
# Для карточек персонажей используется: static/game_catalog/character/vanguard_fighter/hero.png

CATALOG_CATEGORIES = {
    "character": "Карточки персонажей",
    "weapon": "Оружие",
    "gloves": "Перчатки",
    "cloak": "Плащи",
    "earring": "Серьги",
    "necklace": "Ожерелья",
    "belt": "Пояса",
    "bracelet": "Браслеты",
    "ring": "Кольца",
    "totem": "Тотемы",
    "seal": "Печати",
    "hat": "Шляпы",
    "body": "Тело",
    "pants": "Штаны",
    "boots": "Ботинки",
    "symbol": "Символы",
    "artifact": "Артефакты",
}

def _catalog_display_name(path: Path) -> str:
    # Имя файла превращаем в аккуратное название предмета.
    return path.stem.replace("_", " ").replace("-", " ").strip() or "Без названия"


def _catalog_display_name_from_url(image_url: str | None) -> str:
    """Возвращает название предмета из имени файла изображения для шаблонов."""
    if not image_url:
        return ""
    from urllib.parse import unquote, urlparse

    path = unquote(urlparse(image_url).path)
    return Path(path).stem.replace("_", " ").replace("-", " ").strip() or "Без названия"


def _catalog_meta_from_path(category: str, path: Path):
    """Возвращает (class_key, tier) из структуры каталога."""
    rel_parts = path.relative_to(CATALOG_DIR / category).parts
    class_key = "all"
    tier = "T1"

    if category == "character":
        if len(rel_parts) >= 2 and rel_parts[0] in CLASS_OPTIONS:
            class_key = rel_parts[0]
    else:
        # Поддерживаем два варианта структуры для экипировки:
        #   category/<class>/T1/item.png
        #   category/all/T1/item.png
        # А также старый упрощённый вариант:
        #   category/T1/item.png  -> универсальный предмет.
        if len(rel_parts) >= 3 and rel_parts[0] in CLASS_OPTIONS and rel_parts[1] in VALID_TIERS:
            class_key = rel_parts[0]
            tier = rel_parts[1]
        elif len(rel_parts) >= 3 and rel_parts[0] == "all" and rel_parts[1] in VALID_TIERS:
            class_key = "all"
            tier = rel_parts[1]
        elif len(rel_parts) >= 2 and rel_parts[0] in CLASS_OPTIONS:
            class_key = rel_parts[0]
            tier = "T1"
        elif len(rel_parts) >= 2 and rel_parts[0] in VALID_TIERS:
            class_key = "all"
            tier = rel_parts[0]

    return class_key, tier


def sync_catalog(db: Session) -> None:
    """Синхронизирует файлы static/game_catalog с таблицей каталога."""
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    known = {row.filename: row for row in db.query(CatalogImage).all()}
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

    actual_filenames = set()

    for category in CATALOG_CATEGORIES:
        category_dir = CATALOG_DIR / category
        category_dir.mkdir(parents=True, exist_ok=True)
        # Рекурсивно ищем картинки: категория / класс / уровень / файл.
        for path in category_dir.rglob('*'):
            if not path.is_file() or path.suffix.lower() not in allowed:
                continue

            class_key, tier = _catalog_meta_from_path(category, path)
            rel_name = path.relative_to(CATALOG_DIR).as_posix()
            actual_filenames.add(rel_name)
            url = f"/static/game_catalog/{rel_name}"
            display_name = _catalog_display_name(path)
            row = known.get(rel_name)
            if row is None:
                db.add(CatalogImage(
                    name=display_name,
                    category=category,
                    class_key=class_key,
                    tier=tier,
                    filename=rel_name,
                    image_url=url,
                ))
            else:
                row.name = display_name
                row.image_url = url
                row.category = category
                row.class_key = class_key
                row.tier = tier

    # Удаляем записи о файлах, которые больше не существуют на диске.
    # Это важно, если картинку перенесли, например, из T1 в T2:
    # старая запись не должна оставаться в старой вкладке.
    for rel_name, row in known.items():
        if rel_name not in actual_filenames:
            db.delete(row)

    db.commit()


Base.metadata.create_all(bind=engine)

# create_all() не добавляет новые колонки в уже существующую SQLite-базу.
# Поэтому делаем маленькую безопасную миграцию старой базы.
def migrate_user_columns():
    db_path = DATABASE_PATH
    if not db_path.exists():
        return
    columns = {
        "class_key": f"VARCHAR(30) DEFAULT '{DEFAULT_CLASS_KEY}'",
        "role": f"VARCHAR(20) DEFAULT '{DEFAULT_ROLE}'",
        "is_superadmin": "INTEGER DEFAULT 0",
        "active_roster": "INTEGER DEFAULT 0",
        "game_nickname": "VARCHAR(50)",
        "attack": "INTEGER DEFAULT 0",
        "defense": "INTEGER DEFAULT 0",
        "accuracy": "INTEGER DEFAULT 0",
        "character_card": "VARCHAR(255)",
        "weapon": "VARCHAR(255)",
        "gloves": "VARCHAR(255)",
        "cloak": "VARCHAR(255)",
        "earring_1": "VARCHAR(255)",
        "earring_2": "VARCHAR(255)",
        "necklace": "VARCHAR(255)",
        "belt": "VARCHAR(255)",
        "bracelet_1": "VARCHAR(255)",
        "bracelet_2": "VARCHAR(255)",
        "ring_1": "VARCHAR(255)",
        "ring_2": "VARCHAR(255)",
        "totem": "VARCHAR(255)",
        "seal": "VARCHAR(255)",
        "hat": "VARCHAR(255)",
        "body": "VARCHAR(255)",
        "pants": "VARCHAR(255)",
        "boots": "VARCHAR(255)",
        "symbol": "VARCHAR(255)",
        "artifact": "VARCHAR(255)",
    }
    connection = sqlite3.connect(db_path)
    try:
        existing = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")

        # Старые тестовые аккаунты могли содержать прежние классы
        # warrior/mage/hunter. Для новой системы переводим неизвестные
        # значения на первый доступный класс, чтобы профиль не ломался.
        placeholders = ",".join(["?"] * len(CLASS_OPTIONS))
        params = [DEFAULT_CLASS_KEY, *CLASS_OPTIONS.keys()]
        connection.execute(
            f"UPDATE users SET class_key = ? "
            f"WHERE class_key IS NULL OR class_key NOT IN ({placeholders})",
            params,
        )
        role_placeholders = ",".join(["?"] * len(ROLE_OPTIONS))
        role_params = [DEFAULT_ROLE, *ROLE_OPTIONS.keys()]
        connection.execute(
            f"UPDATE users SET role = ? "
            f"WHERE role IS NULL OR role NOT IN ({role_placeholders})",
            role_params,
        )
        connection.commit()
    finally:
        connection.close()


def ensure_superadmin():
    """Гарантирует наличие единственного системного аккаунта Admin."""
    db = next(get_db())
    try:
        admin = db.query(User).filter(User.username == ADMIN_USERNAME).first()
        if admin is None and not ADMIN_INITIAL_PASSWORD:
            return
        if admin is None:
            admin = User(
                username=ADMIN_USERNAME,
                password_hash=hash_password(ADMIN_INITIAL_PASSWORD),
                role="chief",
                is_superadmin=1,
                class_key=DEFAULT_CLASS_KEY,
                attack=0, defense=0, accuracy=0,
            )
            db.add(admin)
        else:
            admin.is_superadmin = 1
            admin.role = "chief"
            # Seed-пароль применяется только при первом создании; существующий
            # пароль пользователя Admin не перезаписываем.
        db.commit()
    finally:
        db.close()


def ensure_clan_settings():
    """Гарантирует существование настроек клана с лимитом активного состава 33."""
    db = next(get_db())
    try:
        setting = db.query(ClanSetting).filter(ClanSetting.id == 1).first()
        if setting is None:
            db.add(ClanSetting(id=1, active_roster_limit=33))
            db.commit()
    finally:
        db.close()


def ensure_event_settings():
    """Гарантирует настройки прав отметки для обоих мероприятий."""
    db = next(get_db())
    try:
        for event_type in EVENT_TYPES:
            row = db.query(EventSetting).filter(EventSetting.event_type == event_type).first()
            if row is None:
                db.add(EventSetting(event_type=event_type, attendance_mode="self"))
        db.commit()
    finally:
        db.close()


def migrate_event_columns():
    db_path = DATABASE_PATH
    if not db_path.exists():
        return
    connection = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(events)")}
        if "event_type" not in columns:
            connection.execute("ALTER TABLE events ADD COLUMN event_type VARCHAR(40) DEFAULT 'evening_prime'")
        connection.commit()
    finally:
        connection.close()


def migrate_event_setting_table():
    db_path = DATABASE_PATH
    if not db_path.exists():
        return
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("""CREATE TABLE IF NOT EXISTS event_settings (
            id INTEGER PRIMARY KEY,
            event_type VARCHAR(40) NOT NULL UNIQUE,
            attendance_mode VARCHAR(20) NOT NULL DEFAULT 'self'
        )""")
        connection.commit()
    finally:
        connection.close()


def migrate_catalog_columns():
    db_path = DATABASE_PATH
    if not db_path.exists():
        return
    connection = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(catalog_images)")}
        if "class_key" not in columns:
            connection.execute("ALTER TABLE catalog_images ADD COLUMN class_key VARCHAR(30)")
        if "tier" not in columns:
            connection.execute("ALTER TABLE catalog_images ADD COLUMN tier VARCHAR(10)")
        connection.execute("UPDATE catalog_images SET class_key = COALESCE(class_key, 'all')")
        connection.execute("UPDATE catalog_images SET tier = COALESCE(tier, 'T1')")
        connection.commit()
    finally:
        connection.close()


migrate_user_columns()
migrate_event_columns()
migrate_event_setting_table()
migrate_catalog_columns()
ensure_clan_settings()
ensure_event_settings()

# Первый проход по каталогу после миграции базы.
_catalog_db = next(get_db())
try:
    sync_catalog(_catalog_db)
finally:
    _catalog_db.close()

app = FastAPI(title="GameSite")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-only-change-this-secret"),
    session_cookie="gamesite_session",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["catalog_name"] = _catalog_display_name_from_url
templates.env.globals["MONTH_NAMES_RU"] = MONTH_NAMES_RU
templates.env.globals["WEEKDAY_NAMES_RU"] = WEEKDAY_NAMES_RU


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def is_superadmin(user: User | None) -> bool:
    return bool(user and int(user.is_superadmin or 0) == 1)


# После объявления функций хеширования создаём/проверяем системный аккаунт.
ensure_superadmin()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    return templates.TemplateResponse(request=request, name="index.html", context={"user": user})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    # Не доверяем одному только user_id в cookie: если пользователь был
    # удалён/база была заменена, старый cookie больше не должен создавать
    # цикл /register -> /profile -> /login -> /profile.
    if current_user(request, db):
        return RedirectResponse("/profile", status_code=303)
    if request.session.get("user_id"):
        request.session.clear()
    return templates.TemplateResponse(request=request, name="register.html", context={"error": None})


@app.post("/register", response_class=HTMLResponse)
async def register(request: Request, username: str = Form(...), password: str = Form(...), password_confirm: str = Form(...), db: Session = Depends(get_db)):
    username = username.strip()
    error = None
    if len(username) < 3 or len(username) > 50:
        error = "Логин должен содержать от 3 до 50 символов."
    elif len(password) < 6:
        error = "Пароль должен содержать минимум 6 символов."
    elif password != password_confirm:
        error = "Пароли не совпадают."
    elif db.query(User).filter(User.username == username).first():
        error = "Пользователь с таким логином уже существует."
    if error:
        return templates.TemplateResponse(request=request, name="register.html", context={"error": error, "username": username}, status_code=400)

    user = User(username=username, password_hash=hash_password(password), class_key=DEFAULT_CLASS_KEY, role=DEFAULT_ROLE, attack=0, defense=0, accuracy=0)
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/profile", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    # Проверяем, что user_id из cookie действительно существует в базе.
    if current_user(request, db):
        return RedirectResponse("/profile", status_code=303)
    if request.session.get("user_id"):
        request.session.clear()
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    username = username.strip()
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(request=request, name="login.html", context={"error": "Неверный логин или пароль.", "username": username}, status_code=401)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/profile", status_code=303)


def _profile_context(user, catalog=None):
    return {
        "user": user,
        "catalog": catalog or {},
        "catalog_categories": CATALOG_CATEGORIES,
        "slot_categories": SLOT_CATEGORIES,
        "class_options": CLASS_OPTIONS,
        "default_class_key": DEFAULT_CLASS_KEY,
        "role_options": ROLE_OPTIONS,
        "role_css_classes": ROLE_CSS_CLASSES,
        "is_superadmin": is_superadmin(user),
    }


@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    sync_catalog(db)
    catalog = {category: db.query(CatalogImage).filter(CatalogImage.category == category).order_by(CatalogImage.name.asc()).all() for category in CATALOG_CATEGORIES}
    return templates.TemplateResponse(request=request, name="profile.html", context={**_profile_context(user, catalog), "active_tab": "profile"})


@app.get("/clan", response_class=HTMLResponse)
async def clan_members(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    all_profiled = (db.query(User)
                    .filter(User.game_nickname.isnot(None), User.game_nickname != "")
                    .all())
    # Иерархия: Глава → Офицеры → Сержанты → Бойцы.
    def roster_sort_key(member):
        return (
            ROLE_PRIORITY.get(member.role or DEFAULT_ROLE, ROLE_PRIORITY[DEFAULT_ROLE]),
            (member.game_nickname or "").casefold(),
        )

    active_members = [m for m in all_profiled if int(m.active_roster or 0) == 1]
    inactive_members = [m for m in all_profiled if int(m.active_roster or 0) != 1]
    active_members.sort(key=roster_sort_key)
    inactive_members.sort(key=roster_sort_key)
    members = active_members

    # Готовим данные экипировки для модального окна состава клана.
    clan_slots = [
        ("weapon", "Оружие"),
        ("gloves", "Перчатки"),
        ("cloak", "Плащ"),
        ("earring_1", "Серьга 1"),
        ("earring_2", "Серьга 2"),
        ("necklace", "Ожерелье"),
        ("belt", "Пояс"),
        ("bracelet_1", "Браслет 1"),
        ("bracelet_2", "Браслет 2"),
        ("ring_1", "Кольцо 1"),
        ("ring_2", "Кольцо 2"),
        ("totem", "Тотем"),
        ("seal", "Печать"),
        ("hat", "Шляпа"),
        ("body", "Тело"),
        ("pants", "Штаны"),
        ("boots", "Ботинки"),
        ("symbol", "Символ"),
        ("artifact", "Артефакт"),
    ]
    def build_members_view(source_members):
        views = []
        for member in source_members:
            equipment = []
            for field, label in clan_slots:
                image_url = getattr(member, field, None)
                equipment.append({
                    "field": field,
                    "label": label,
                    "image_url": image_url,
                    "name": _catalog_display_name_from_url(image_url) if image_url else "Пусто",
                })
            views.append({
                "user": {
                    "id": member.id,
                    "game_nickname": member.game_nickname,
                    "class_key": member.class_key,
                    "character_card": member.character_card,
                    "attack": member.attack or 0,
                    "defense": member.defense or 0,
                    "accuracy": member.accuracy or 0,
                    "role": member.role or DEFAULT_ROLE,
                    "role_name": ROLE_OPTIONS.get(member.role or DEFAULT_ROLE, ROLE_OPTIONS[DEFAULT_ROLE]),
                    "active_roster": int(member.active_roster or 0) == 1,
                },
                "equipment": equipment,
            })
        return views

    members_view = build_members_view(active_members)
    inactive_members_view = build_members_view(inactive_members)
    setting = db.query(ClanSetting).filter(ClanSetting.id == 1).first()
    active_limit = setting.active_roster_limit if setting else 33

    return templates.TemplateResponse(
        request=request,
        name="clan.html",
        context={
            **_profile_context(user),
            "members": active_members,
            "members_view": members_view,
            "inactive_members": inactive_members,
            "inactive_members_view": inactive_members_view,
            "active_limit": active_limit,
            "active_tab": "clan",
        },
    )


def _validate_event_type(event_type: str) -> str:
    if event_type not in EVENT_TYPES:
        raise HTTPException(status_code=404, detail="Неизвестное мероприятие")
    return event_type


def _month_calendar(year: int, month: int):
    weeks = calendar.monthcalendar(year, month)
    result = []
    for week in weeks:
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(None)
            else:
                d = date(year, month, day_num)
                row.append({
                    "iso": d.isoformat(),
                    "day": day_num,
                    "weekday": WEEKDAY_NAMES_RU[d.weekday()],
                    "weekday_index": d.weekday(),
                })
        result.append(row)
    return result


def _get_attendance_mode(db: Session, event_type: str) -> str:
    setting = db.query(EventSetting).filter(EventSetting.event_type == event_type).first()
    return setting.attendance_mode if setting and setting.attendance_mode in ATTENDANCE_MODES else "self"


def _active_members(db: Session):
    members = (db.query(User)
               .filter(User.active_roster == 1, User.game_nickname.isnot(None), User.game_nickname != "")
               .all())
    members.sort(key=lambda member: (
        ROLE_PRIORITY.get(member.role or DEFAULT_ROLE, ROLE_PRIORITY[DEFAULT_ROLE]),
        (member.game_nickname or "").casefold(),
    ))
    return members


def _event_for_date(db: Session, event_type: str, event_date: str, create: bool = False):
    row = (db.query(Event)
           .filter(Event.event_type == event_type, Event.event_date == event_date)
           .first())
    if row is None and create:
        row = Event(name=EVENT_TYPES[event_type], event_date=event_date, event_type=event_type)
        db.add(row)
        db.flush()
    return row


def _event_page_context(user: User, event_type: str, year: int, month: int, db: Session):
    current = date.today()
    if year < 2020 or year > current.year + 5:
        year = current.year
    if month < 1 or month > 12:
        month = current.month
    selected = _event_for_date(db, event_type, current.isoformat(), create=False)
    return {
        **_profile_context(user),
        "event_type": event_type,
        "event_title": EVENT_TYPES[event_type],
        "attendance_mode": _get_attendance_mode(db, event_type),
        "attendance_mode_name": ATTENDANCE_MODES[_get_attendance_mode(db, event_type)],
        "calendar": _month_calendar(year, month),
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES_RU[month - 1],
        "prev_year": year - 1 if month == 1 else year,
        "prev_month": 12 if month == 1 else month - 1,
        "next_year": year + 1 if month == 12 else year,
        "next_month": 1 if month == 12 else month + 1,
        "today_iso": current.isoformat(),
        "active_tab": event_type,
    }


@app.get("/events", response_class=HTMLResponse)
async def events_redirect(request: Request):
    return RedirectResponse("/events/evening_prime", status_code=303)


@app.get("/events/day")
async def event_day_data(request: Request, event_type: str, event_date: str, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    event_type = _validate_event_type(event_type)
    try:
        parsed = date.fromisoformat(event_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректная дата")
    event = _event_for_date(db, event_type, parsed.isoformat(), create=False)
    present_ids = set()
    if event:
        present_ids = {r.user_id for r in db.query(EventAttendance).filter(EventAttendance.event_id == event.id, EventAttendance.status == "present").all()}
    mode = _get_attendance_mode(db, event_type)
    members = _active_members(db)
    return {
        "event_type": event_type,
        "event_name": EVENT_TYPES[event_type],
        "event_date": parsed.isoformat(),
        "event_date_display": parsed.strftime("%d.%m.%Y"),
        "attendance_mode": mode,
        "can_edit_any": is_superadmin(user),
        "current_user_id": user.id,
        "players": [
            {
                "id": m.id,
                "nickname": m.game_nickname,
                "role": ROLE_OPTIONS.get(m.role or DEFAULT_ROLE, ROLE_OPTIONS[DEFAULT_ROLE]),
                "role_key": m.role or DEFAULT_ROLE,
                "character_card": m.character_card,
                "class_key": m.class_key or DEFAULT_CLASS_KEY,
                "present": m.id in present_ids,
            } for m in members
        ],
    }


@app.post("/events/attendance")
async def save_event_attendance(
    request: Request,
    event_type: str = Form(...),
    event_date: str = Form(...),
    user_id: int = Form(...),
    present: str = Form("1"),
    db: Session = Depends(get_db),
):
    actor = current_user(request, db)
    if not actor:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    event_type = _validate_event_type(event_type)
    try:
        parsed = date.fromisoformat(event_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректная дата")

    target = db.query(User).filter(User.id == user_id, User.active_roster == 1).first()
    if not target or not target.game_nickname:
        raise HTTPException(status_code=400, detail="Игрок не входит в активный состав")

    mode = _get_attendance_mode(db, event_type)
    if not is_superadmin(actor):
        if mode != "self" or actor.id != target.id:
            raise HTTPException(status_code=403, detail="Сейчас отмечать присутствие может только игрок сам за себя")

    event = _event_for_date(db, event_type, parsed.isoformat(), create=True)
    row = db.query(EventAttendance).filter(EventAttendance.event_id == event.id, EventAttendance.user_id == target.id).first()
    should_present = str(present).lower() in {"1", "true", "on", "yes"}
    if should_present:
        if row is None:
            db.add(EventAttendance(event_id=event.id, user_id=target.id, status="present"))
        else:
            row.status = "present"
    elif row is not None:
        db.delete(row)
    db.commit()
    return {"ok": True, "user_id": target.id, "present": should_present}


@app.get("/events/{event_type}", response_class=HTMLResponse)
async def event_page(request: Request, event_type: str, year: int | None = None, month: int | None = None, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    event_type = _validate_event_type(event_type)
    today = date.today()
    year = year or today.year
    month = month or today.month
    return templates.TemplateResponse(
        request=request,
        name="event_calendar.html",
        context=_event_page_context(user, event_type, year, month, db),
    )

@app.get("/attendance-stats", response_class=HTMLResponse)
async def attendance_stats(request: Request, period: str = "month", event_type: str = "all", db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if period not in {"week", "month", "all"}:
        period = "month"
    if event_type not in {"all", *EVENT_TYPES.keys()}:
        event_type = "all"

    today = date.today()
    if period == "week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif period == "month":
        start = today.replace(day=1)
        end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    else:
        start = None
        end = None

    q = db.query(EventAttendance, Event, User).join(Event, EventAttendance.event_id == Event.id).join(User, User.id == EventAttendance.user_id).filter(EventAttendance.status == "present")
    if event_type != "all":
        q = q.filter(Event.event_type == event_type)
    if start and end:
        q = q.filter(Event.event_date >= start.isoformat(), Event.event_date <= end.isoformat())

    rows = q.all()
    aggregate = {}
    for attendance, event, member in rows:
        bucket = aggregate.setdefault(member.id, {
            "user": member,
            "evening_prime": 0,
            "guild_dungeon": 0,
            "total": 0,
        })
        if event.event_type in EVENT_TYPES:
            bucket[event.event_type] += 1
            bucket["total"] += 1

    summary = sorted(aggregate.values(), key=lambda x: (-x["total"], (x["user"].game_nickname or x["user"].username).casefold()))
    totals = {"evening_prime": sum(x["evening_prime"] for x in summary), "guild_dungeon": sum(x["guild_dungeon"] for x in summary)}
    totals["total"] = totals["evening_prime"] + totals["guild_dungeon"]

    return templates.TemplateResponse(
        request=request,
        name="attendance_stats.html",
        context={
            **_profile_context(user),
            "active_tab": "attendance_stats",
            "period": period,
            "event_type_filter": event_type,
            "period_label": {"week":"Текущая неделя", "month":"Текущий месяц", "all":"За всё время"}[period],
            "range_start": start.strftime("%d.%m.%Y") if start else "—",
            "range_end": end.strftime("%d.%m.%Y") if end else "—",
            "summary": summary,
            "totals": totals,
            "event_types": EVENT_TYPES,
        },
    )


@app.get("/valuable-items", response_class=HTMLResponse)
async def valuable_items_page(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    items = db.query(ValuableItem).order_by(ValuableItem.id.desc()).all()
    users = {u.id: u for u in db.query(User).all()}
    return templates.TemplateResponse(
        request=request,
        name="valuable_items.html",
        context={**_profile_context(user), "items": items, "users": users, "active_tab": "valuable"},
    )


def _user_upload_dir(user_id: int) -> Path:
    path = UPLOAD_DIR / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _remove_saved_image(url: str | None, user_id: int) -> None:
    if not url or not url.startswith("/static/uploads/"):
        return
    relative = url.removeprefix("/static/uploads/")
    path = (UPLOAD_DIR / relative).resolve()
    user_root = _user_upload_dir(user_id).resolve()
    try:
        path.relative_to(user_root)
    except ValueError:
        return
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass


@app.get("/profile/catalog/{slot}")
async def profile_catalog(request: Request, slot: str, tier: str = "T1", db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    category = SLOT_CATEGORIES.get(slot)
    if not category:
        raise HTTPException(status_code=400, detail="Неизвестный слот")

    sync_catalog(db)
    class_key = user.class_key or DEFAULT_CLASS_KEY
    query = db.query(CatalogImage).filter(CatalogImage.category == category)

    # Для персонажа показываем только карточки выбранного класса.
    # Для предметов показываем выбранный класс + универсальные предметы (all).
    query = query.filter((CatalogImage.class_key == class_key) | (CatalogImage.class_key == "all"))

    if category != "character":
        tier = tier.upper()
        if tier not in VALID_TIERS:
            raise HTTPException(status_code=400, detail="Неизвестный тир")
        query = query.filter((CatalogImage.tier == tier) | (CatalogImage.tier.is_(None)))
    else:
        tier = None

    items = query.order_by(CatalogImage.name.asc()).all()
    return {
        "slot": slot,
        "category": category,
        "title": CATALOG_CATEGORIES[category],
        "class_key": class_key,
        "class_name": CLASS_OPTIONS.get(class_key, class_key),
        "tier": tier,
        "count": len(items),
        "items": [
            {"id": item.id, "name": item.name, "image_url": item.image_url, "tier": item.tier or "T1"}
            for item in items
        ],
    }


@app.post("/profile/select-image")
async def select_profile_image(
    request: Request,
    slot: str = Form(...),
    catalog_id: int = Form(...),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    if slot not in IMAGE_FIELDS:
        raise HTTPException(status_code=400, detail="Неизвестный слот")

    category = SLOT_CATEGORIES.get(slot)
    image = db.query(CatalogImage).filter(CatalogImage.id == catalog_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Изображение не найдено в каталоге")
    if image.category != category:
        raise HTTPException(status_code=400, detail="Это изображение нельзя использовать в данном слоте")

    allowed_class = user.class_key or DEFAULT_CLASS_KEY
    if image.class_key not in (allowed_class, "all", None):
        raise HTTPException(status_code=400, detail="Это изображение относится к другому классу")

    setattr(user, IMAGE_FIELDS[slot], image.image_url)
    db.commit()
    return {"ok": True, "slot": slot, "url": image.image_url}


@app.post("/profile/delete-image")
async def delete_profile_image(
    request: Request,
    slot: str = Form(...),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    if slot not in IMAGE_FIELDS:
        raise HTTPException(status_code=400, detail="Неизвестный слот")

    field_name = IMAGE_FIELDS[slot]
    old_url = getattr(user, field_name, None)
    setattr(user, field_name, None)
    db.commit()
    _remove_saved_image(old_url, user.id)
    return {"ok": True, "slot": slot}


@app.post("/profile/set-class")
async def set_profile_class(
    request: Request,
    class_key: str = Form(...),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    if class_key not in CLASS_OPTIONS:
        raise HTTPException(status_code=400, detail="Неизвестный класс")
    user.class_key = class_key
    db.commit()
    return {"ok": True, "class_key": class_key, "class_name": CLASS_OPTIONS[class_key]}


@app.post("/profile/save")
async def save_profile(
    request: Request,
    game_nickname: str = Form(""),
    attack: str = Form("0"),
    defense: str = Form("0"),
    accuracy: str = Form("0"),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    def safe_stat(value: str) -> int:
        try:
            return max(0, int(value.strip() or "0"))
        except (ValueError, AttributeError):
            return 0

    user.game_nickname = game_nickname.strip()[:50]
    user.attack = safe_stat(attack)
    user.defense = safe_stat(defense)
    user.accuracy = safe_stat(accuracy)
    db.commit()
    return RedirectResponse("/profile?saved=1", status_code=303)


@app.get("/admin/active-roster", response_class=HTMLResponse)
async def admin_active_roster_page(request: Request, db: Session = Depends(get_db)):
    admin = current_user(request, db)
    if not admin:
        return RedirectResponse("/login", status_code=303)
    if not is_superadmin(admin):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    members = (db.query(User)
               .filter(User.game_nickname.isnot(None), User.game_nickname != "")
               .all())
    members.sort(key=lambda member: (
        ROLE_PRIORITY.get(member.role or DEFAULT_ROLE, ROLE_PRIORITY[DEFAULT_ROLE]),
        (member.game_nickname or "").casefold(),
    ))
    setting = db.query(ClanSetting).filter(ClanSetting.id == 1).first()
    limit = setting.active_roster_limit if setting else 33
    active_count = sum(1 for m in members if int(m.active_roster or 0) == 1)
    return templates.TemplateResponse(
        request=request,
        name="active_roster.html",
        context={
            **_profile_context(admin),
            "members": members,
            "active_limit": limit,
            "active_count": active_count,
            "role_priority": ROLE_PRIORITY,
            "active_tab": "active_roster",
            "saved": request.query_params.get("saved"),
            "error": request.query_params.get("error"),
        },
    )


@app.post("/admin/active-roster/save")
async def admin_active_roster_save(
    request: Request,
    active_user_ids: list[int] | None = Form(None),
    active_roster_limit: int = Form(...),
    db: Session = Depends(get_db),
):
    admin = current_user(request, db)
    if not admin:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    if not is_superadmin(admin):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    limit = max(1, min(int(active_roster_limit or 33), 999))
    selected_ids = set(active_user_ids or [])
    existing_users = db.query(User).all()
    selected_real = {u.id for u in existing_users if u.id in selected_ids and u.game_nickname and u.game_nickname.strip()}
    if len(selected_real) > limit:
        return RedirectResponse(f"/admin/active-roster?error=selected_limit", status_code=303)

    setting = db.query(ClanSetting).filter(ClanSetting.id == 1).first()
    if setting is None:
        setting = ClanSetting(id=1, active_roster_limit=limit)
        db.add(setting)
    setting.active_roster_limit = limit

    for member in existing_users:
        member.active_roster = 1 if member.id in selected_real else 0

    db.commit()
    return RedirectResponse("/admin/active-roster?saved=1", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not is_superadmin(user):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    members = db.query(User).order_by(User.username.asc()).all()
    attendance_settings = {
        row.event_type: row.attendance_mode
        for row in db.query(EventSetting).all()
        if row.event_type in EVENT_TYPES
    }
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            **_profile_context(user),
            "members": members,
            "active_tab": "admin",
            "admin_roles": ROLE_OPTIONS,
            "event_types": EVENT_TYPES,
            "attendance_modes": ATTENDANCE_MODES,
            "attendance_settings": attendance_settings,
        },
    )


@app.post("/admin/set-attendance-permission")
async def admin_set_attendance_permission(
    request: Request,
    event_type: str = Form(...),
    attendance_mode: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = current_user(request, db)
    if not admin or not is_superadmin(admin):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    _validate_event_type(event_type)
    if attendance_mode not in ATTENDANCE_MODES:
        raise HTTPException(status_code=400, detail="Неизвестный режим отметки")
    row = db.query(EventSetting).filter(EventSetting.event_type == event_type).first()
    if row is None:
        row = EventSetting(event_type=event_type, attendance_mode=attendance_mode)
        db.add(row)
    else:
        row.attendance_mode = attendance_mode
    db.commit()
    return RedirectResponse("/admin?saved=attendance", status_code=303)


@app.post("/admin/set-role")
async def admin_set_role(
    request: Request,
    user_id: int = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = current_user(request, db)
    if not admin:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    if not is_superadmin(admin):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    if role not in ROLE_OPTIONS:
        raise HTTPException(status_code=400, detail="Неизвестная должность")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    # Системный Admin остаётся Главой и не может быть понижен через панель.
    if target.username == ADMIN_USERNAME:
        target.role = "chief"
        target.is_superadmin = 1
    else:
        target.role = role
    db.commit()
    return RedirectResponse("/admin?saved=1", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
