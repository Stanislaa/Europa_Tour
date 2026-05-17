"""Наполнение БД тестовыми данными.

Можно запускать двумя способами:
  1. Напрямую:  python seed.py
  2. Автоматически при старте сервера — функция seed() вызывается из lifespan
     в main.py, если база пустая (нужно для хостинга, где нет доступа к консоли).
"""
from decimal import Decimal
from sqlmodel import Session, select
from main import engine, Country, Hotel, Tour, SQLModel

COUNTRIES = [
    ("Турция", "TR", False),
    ("ОАЭ", "AE", False),
    ("Египет", "EG", False),
    ("Таиланд", "TH", False),
    ("Греция", "GR", True),
    ("Россия", "RU", False),
    ("Грузия", "GE", False),
    ("Кипр", "CY", True),
]

TOURS = [
    # (country_code, hotel_name, city, stars, title, price, board, desc, img)
    ("TR", "Rixos Premium Belek", "Анталья", 5, "Турция, Анталья — отдых на песчаном пляже",
     8500, "AI", "Премиальный отель «всё включено» на первой береговой линии. Большая территория, аквапарк, развитая инфраструктура для семей с детьми.",
     "https://images.unsplash.com/photo-1519046904884-53103b34b206?w=800"),
    ("TR", "Hilton Dalaman", "Даламан", 5, "Турция, Даламан — спокойный пляжный отдых",
     7200, "UAI", "Уединённый отель в окружении соснового леса, частный пляж, СПА-комплекс, теннисные корты.",
     "https://images.unsplash.com/photo-1559599189-fe84dea4eb79?w=800"),
    ("AE", "Atlantis The Palm", "Дубай", 5, "ОАЭ, Дубай — отдых класса люкс",
     14500, "BB", "Легендарный отель на пальме Джумейра, аквапарк Aquaventure, океанариум, рестораны мишленовских шефов.",
     "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=800"),
    ("AE", "JA Beach Hotel", "Дубай", 4, "ОАЭ, Дубай — семейный отдых",
     9800, "HB", "Большой пляжный комплекс с собственным заливом, водный спорт, конный клуб, гольф-поле.",
     "https://images.unsplash.com/photo-1582719508461-905c673771fd?w=800"),
    ("EG", "Sunrise Crystal Bay", "Хургада", 5, "Египет, Хургада — пляжный отдых и Красное море",
     6200, "AI", "Отель на собственном пляже с коралловым рифом, прекрасные условия для дайвинга и снорклинга.",
     "https://images.unsplash.com/photo-1602002418082-a4443e081dd1?w=800"),
    ("EG", "Steigenberger Aldau", "Хургада", 5, "Египет, Хургада — Steigenberger",
     6800, "AI", "Современный отель с большой территорией, два бассейна, гольф-поле в шаговой доступности.",
     "https://images.unsplash.com/photo-1571003123894-1f0594d2b5d9?w=800"),
    ("TH", "Centara Grand Phuket", "Пхукет", 5, "Таиланд, Пхукет — экзотический пляжный отдых",
     11500, "BB", "Уютный отель в бухте Karon, тропический сад, СПА, экскурсии на острова Пхи-Пхи и Симиланские.",
     "https://images.unsplash.com/photo-1552465011-b4e21bf6e79a?w=800"),
    ("TH", "Banyan Tree Krabi", "Краби", 5, "Таиланд, Краби — отдых в Андаманском море",
     12800, "BB", "Бутик-отель в национальном парке, виллы с собственными бассейнами, кухня высочайшего уровня.",
     "https://images.unsplash.com/photo-1540541338287-41700207dee6?w=800"),
    ("GR", "Aldemar Knossos", "Крит", 5, "Греция, Крит — Эгейское море и античная история",
     9400, "AI", "Просторный комплекс на Крите, экскурсии в Кносский дворец, традиционная кухня, идеален для пар.",
     "https://images.unsplash.com/photo-1503152394-c571994fd383?w=800"),
    ("GR", "Costa Navarino", "Пелопоннес", 5, "Греция, Пелопоннес — Costa Navarino",
     13200, "HB", "Современный курорт у моря Иония, два чемпионских гольф-поля, разнообразные СПА-программы.",
     "https://images.unsplash.com/photo-1530541930197-ff16ac917b0e?w=800"),
    ("RU", "Mriya Resort", "Ялта", 5, "Россия, Крым — Mriya Resort",
     8700, "BB", "Современный курортный комплекс на южном берегу Крыма, аквапарк, СПА, виноградники, морские прогулки.",
     "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800"),
    ("RU", "Радиссон Сочи", "Сочи", 5, "Россия, Сочи — Радиссон",
     7500, "BB", "Гостиница в центре Сочи у моря, до парка Ривьера 5 минут пешком, рестораны, СПА, конференц-залы.",
     "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=800"),
    ("GE", "Rooms Hotel Tbilisi", "Тбилиси", 4, "Грузия, Тбилиси — городской отдых",
     5400, "BB", "Стильный бутик-отель в центре Тбилиси, рядом старый город, серные бани, прогулки по Мтацминде.",
     "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800"),
    ("CY", "Anassa", "Пафос", 5, "Кипр, Пафос — Anassa",
     12100, "HB", "Изысканный курорт в стиле средиземноморской деревни, частный пляж, СПА-центр уровня премиум.",
     "https://images.unsplash.com/photo-1571003123894-1f0594d2b5d9?w=800"),
]


def seed() -> str:
    """Создаёт таблицы и наполняет БД, если она пустая. Возвращает текст-результат."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        if db.exec(select(Country)).first():
            return "База уже содержит данные — наполнение пропущено."
        codes = {}
        for name, code, visa in COUNTRIES:
            c = Country(name=name, code=code, visa_required=visa)
            db.add(c); db.commit(); db.refresh(c)
            codes[code] = c.id
        for code, hname, city, stars, title, price, board, desc, img in TOURS:
            h = Hotel(country_id=codes[code], name=hname, city=city, star_rating=stars)
            db.add(h); db.commit(); db.refresh(h)
            t = Tour(
                title=title, country_id=codes[code], hotel_id=h.id,
                nights_min=7, nights_max=14, board_type=board,
                price_per_night=Decimal(price), description=desc, image_url=img,
            )
            db.add(t); db.commit()
        return f"Создано {len(COUNTRIES)} стран и {len(TOURS)} туров."


if __name__ == "__main__":
    print(seed())
