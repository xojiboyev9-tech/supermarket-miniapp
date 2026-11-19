import pandas as pd
from database import SessionLocal, Category, Product, init_db

CATEGORY_RULES = [
    ("Go'sht va kolbasa", "🥩", ["КОЛБ", "ВЕТЧИНА", "СОСИСКИ", "МЯСО", "ГОВЯДИНА", "КУРИЦ", "ИНДЕЙКА", "ФАРШ", "ТЕГЕН", "ШАМС"]),
    ("Sut mahsulotlari", "🥛", ["СЫР", "МОЛОКО", "КЕФИР", "ТВОРОГ", "СМЕТАНА", "ЙОГУРТ", "МАСЛО СЛИВ", "СЛИВ. МАСЛО", "СЫРОК", "БРЫНЗА"]),
    ("Non mahsulotlari", "🥖", ["ХЛЕБ", "БАТОН", "БУЛОЧ", "ЛЕПЕШ", "ЛАВАШ", "СУХАР"]),
    ("Meva-sabzavot", "🍎", ["КАРТОШ", "ЛУК", "МОРКОВ", "ЯБЛОК", "БАНАН", "АПЕЛЬСИН", "КИВИ", "ГРАНАТ", "ПОМИДОР", "ОГУРЦ", "ЛИМОН"]),
    ("Qandolat mahsulotlari", "🍫", ["КОНФ", "ПЕЧЕНЬЕ", "ШОКОЛАД", "ВАФЛИ", "ТОРТ", "РУЛЕТ", "ЗЕФИР", "МАРМЕЛАД", "РОШЕН", "КОНТИ"]),
    ("Ichimliklar", "🥤", ["ВОДА", "СОК", "КОЛА", "ПЕПСИ", "ЧАЙ", "КОФЕ", "НАПИТОК", "ЛИМОНАД", "ЭНЕРГЕТИК"]),
    ("Oziq-ovqat va donlar", "🌾", ["ГРЕЧКА", "РИС", "САХАР", "МУКА", "МАКАРОН", "МАСЛО РАСТ", "ПОДСОЛН", "СОЛЬ", "КРУПА", "ГОРОХ"]),
    ("Maishiy kimyo va gigiyena", "🧼", ["ШАМПУНЬ", "МЫЛО", "СОВУН", "ПОРОШОК", "ПРОКЛАДКИ", "ГЕЛЬ", "БРИТВА", "БУМАГА", "ЗУБН", "ЧИСТОЛЬ"]),
]

def detect_category(name: str) -> tuple[str, str]:
    upper_name = str(name).upper()
    for cat_name, icon, keywords in CATEGORY_RULES:
        if any(kw in upper_name for kw in keywords):
            return cat_name, icon
    return "Boshqa mahsulotlar", "📦"

def run_import(csv_path="tahlil.csv", only_positive_stock=True):
    init_db()
    db = SessionLocal()
    df = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig")
    
    # Narxi 0 dan katta bo'lgan tovarlarni filtrlash
    df = df[df["sotuv_narxi"] > 0]
    if only_positive_stock:
        df = df[df["qoldiq"] > 0]

    cat_cache = {}
    for cat in db.query(Category).all():
        cat_cache[cat.name] = cat.id

    added = 0
    for _, row in df.iterrows():
        cat_name, icon = detect_category(row["nomi"])
        if cat_name not in cat_cache:
            new_cat = Category(name=cat_name, icon=icon)
            db.add(new_cat)
            db.commit()
            db.refresh(new_cat)
            cat_cache[cat_name] = new_cat.id

        unit = str(row["birlik"]).strip() if pd.notna(row["birlik"]) else "шт."
        if unit not in ["шт.", "кг."]:
            unit = "шт."
        is_weighted = (str(row["ogirlikli"]).strip().lower() == "ha") or (unit == "кг.")

        prod = Product(
            code=str(row["kod"]),
            name=str(row["nomi"]).strip(),
            category_id=cat_cache[cat_name],
            price=float(row["sotuv_narxi"]),
            unit=unit,
            is_weighted=is_weighted,
            stock=float(row["qoldiq"]),
            is_approved=True
        )
        db.add(prod)
        added += 1
        if added % 500 == 0:
            db.commit()

    db.commit()
    db.close()
    print(f"Muvaffaqiyatli yuklandi: {added} ta mahsulot.")

if __name__ == "__main__":
    run_import()
  
