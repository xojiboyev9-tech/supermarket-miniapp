import os
import json
import random
import asyncio
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from database import SessionLocal, init_db, User, Category, Product, ProductRequest, Order, StoreSettings
from import_csv import run_import

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-cloud-run-url.a.run.app")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "123456789"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI(title="Supermarket MiniApp API")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- TELEGRAM BOT HANDLERLARI ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user:
        role = "super_admin" if message.from_user.id == SUPER_ADMIN_ID else "customer"
        user = User(telegram_id=message.from_user.id, full_name=message.from_user.full_name, role=role)
        db.add(user)
        db.commit()

    if not user.phone:
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            "Assalomu alaykum! Supermarket onlayn buyurtma botiga xush kelibsiz.\n\n"
            "Buyurtma berish va navbatsiz olib ketish uchun avval telefon raqamingizni yuboring:",
            reply_markup=kb
        )
    else:
        await send_main_menu(message, user.role)
    db.close()

@dp.message(F.contact)
async def handle_contact(message: types.Message):
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if user:
        user.phone = message.contact.phone_number
        db.commit()
        await message.answer("✅ Telefon raqamingiz saqlandi!", reply_markup=types.ReplyKeyboardRemove())
        await send_main_menu(message, user.role)
    db.close()

async def send_main_menu(message: types.Message, role: str):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Do'konni ochish (Mini App)", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    role_text = {
        "super_admin": "👑 Siz Super Admin sifatida kirdingiz.",
        "admin": "🛡 Siz Admin sifatida kirdingiz.",
        "worker": "👨‍🍳 Siz Bo'lim ishchisi sifatida kirdingiz.",
        "customer": "🛍 Katalogdan mahsulotlarni tanlang va navbatsiz olib keting!"
    }.get(role, "")
    await message.answer(f"{role_text}\n\nIlovani ochish uchun quyidagi tugmani bosing:", reply_markup=kb)

# Mijoz buyurtma bergandan so'ng to'g'ridan-to'g'ri savol yoki rasm yuborishi
@dp.message(F.photo | F.text)
async def forward_customer_inquiry(message: types.Message):
    if message.text and message.text.startswith("/"):
        return
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user:
        db.close()
        return

    # Agar Admin javob qaytarayotgan bo'lsa (Reply orqali)
    if user.role in ["super_admin", "admin"] and message.reply_to_message:
        orig_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        if "ID:" in orig_text:
            try:
                target_id = int(orig_text.split("ID:")[1].split()[0].strip())
                if message.photo:
                    await bot.send_photo(target_id, message.photo[-1].file_id, caption=f"📩 Admin javobi:\n{message.caption or ''}")
                else:
                    await bot.send_message(target_id, f"📩 Admin javobi:\n{message.text}")
                await message.answer("✅ Javob mijozga yuborildi.")
            except Exception as e:
                await message.answer(f"Xatolik: {e}")
        db.close()
        return

    # Mijoz yozgan xabar yoki rasmni barcha adminlarga yuborish
    if user.role == "customer":
        last_order = db.query(Order).filter(Order.user_id == user.telegram_id).order_by(Order.id.desc()).first()
        order_info = f"Buyurtma: {last_order.order_code}" if last_order else "Buyurtma yo'q"
        admins = db.query(User).filter(User.role.in_(["super_admin", "admin"])).all()
        header = f"💬 Mijozdan murojaat!\n👤 {user.full_name} ({user.phone})\n🆔 ID:{user.telegram_id} | {order_info}\n\n"
        for adm in admins:
            try:
                if message.photo:
                    await bot.send_photo(adm.telegram_id, message.photo[-1].file_id, caption=header + (message.caption or ""))
                else:
                    await bot.send_message(adm.telegram_id, header + message.text)
            except Exception:
                pass
        await message.answer("✅ Xabaringiz/rasmingiz adminga yuborildi. Tez orada javob berishadi!")
    db.close()

# --- API ENDPOINTLAR (MINI APP UCHUN) ---

class OrderCreate(BaseModel):
    user_id: int
    items: list
    total_amount: float
    delivery_type: str = "pickup"
    delivery_address: Optional[str] = None

class RoleAssign(BaseModel):
    admin_id: int
    target_telegram_id: int
    role: str
    category_id: Optional[int] = None

class WorkerProductReq(BaseModel):
    worker_id: int
    category_id: int
    product_id: Optional[int] = None
    action: str
    name: str
    price: float
    unit: str = "шт."
    image_url: Optional[str] = None

@app.get("/")
async def serve_app():
    return FileResponse("static/index.html")

@app.get("/api/init/{telegram_id}")
def get_init_data(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        role = "super_admin" if telegram_id == SUPER_ADMIN_ID else "customer"
        user = User(telegram_id=telegram_id, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    categories = db.query(Category).filter(Category.is_active == True).all()
    settings = db.query(StoreSettings).first()
    return {
        "user": {
            "telegram_id": user.telegram_id,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": user.role,
            "assigned_category_id": user.assigned_category_id
        },
        "categories": categories,
        "settings": settings
    }

@app.get("/api/products")
def get_products(category_id: Optional[int] = None, search: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Product).filter(Product.is_approved == True)
    if category_id:
        q = q.filter(Product.category_id == category_id)
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%"))
    return q.limit(100).all()

@app.post("/api/orders")
async def create_order(data: OrderCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == data.user_id).first()
    if not user or not user.phone:
        raise HTTPException(status_code=400, detail="Avval botda telefon raqamingizni yuboring!")
    
    order_code = f"#A{random.randint(10000, 99999)}"
    new_order = Order(
        order_code=order_code,
        user_id=user.telegram_id,
        customer_phone=user.phone,
        items_json=json.dumps(data.items, ensure_ascii=False),
        total_amount=data.total_amount,
        delivery_type=data.delivery_type,
        delivery_address=data.delivery_address,
        status="new"
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # Adminlarga xabar yuborish
    items_text = "\n".join([f"• {i['name']} x {i['qty']} {i['unit']} = {i['price']*i['qty']:,.0f} so'm" for i in data.items])
    msg = (
        f"🆕 <b>Yangi buyurtma: {order_code}</b>\n"
        f"👤 Mijoz: {user.full_name}\n"
        f"📞 Tel: {user.phone}\n"
        f"🚚 Usul: {'Olib ketish' if data.delivery_type == 'pickup' else 'Yetkazib berish'}\n\n"
        f"{items_text}\n\n"
        f"💰 <b>Jami: {data.total_amount:,.0f} so'm</b>"
    )
    admins = db.query(User).filter(User.role.in_(["super_admin", "admin"])).all()
    for adm in admins:
        try:
            await bot.send_message(adm.telegram_id, msg, parse_mode="HTML")
        except Exception:
            pass
    return {"status": "ok", "order_code": order_code}

@app.get("/api/orders/{user_id}")
def get_user_orders(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == user_id).first()
    if user and user.role in ["super_admin", "admin"]:
        return db.query(Order).order_by(Order.id.desc()).limit(100).all()
    return db.query(Order).filter(Order.user_id == user_id).order_by(Order.id.desc()).all()

@app.post("/api/orders/{order_id}/status")
async def update_order_status(order_id: int, status: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    order.status = status
    db.commit()

    status_messages = {
        "accepted": f"✅ Sizning {order.order_code} raqamli buyurtmangiz qabul qilindi va yig'ilmoqda!",
        "ready": f"🎉 {order.order_code} raqamli buyurtmangiz TAYYOR! Do'konga kelib ID yoki telefon raqamingiz ({order.customer_phone}) orqali navbatsiz olib ketishingiz mumkin.",
        "completed": f"🤝 {order.order_code} buyurtmangiz topshirildi. Xaridingiz uchun rahmat!",
        "cancelled": f"❌ {order.order_code} raqamli buyurtmangiz bekor qilindi."
    }
    if status in status_messages:
        try:
            await bot.send_message(order.user_id, status_messages[status])
        except Exception:
            pass
    return {"status": "ok"}

# --- ISHCHI SO'ROVLARI VA ADMIN TASDIQLASHI ---

@app.post("/api/worker/request")
async def create_worker_request(req: WorkerProductReq, db: Session = Depends(get_db)):
    worker = db.query(User).filter(User.telegram_id == req.worker_id).first()
    if not worker or worker.role not in ["worker", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
    if worker.role == "worker" and worker.assigned_category_id != req.category_id:
        raise HTTPException(status_code=403, detail="Siz faqat o'z bo'limingizga mahsulot qo'sha olasiz!")

    new_req = ProductRequest(**req.dict())
    db.add(new_req)
    db.commit()

    admins = db.query(User).filter(User.role.in_(["super_admin", "admin"])).all()
    for adm in admins:
        try:
            await bot.send_message(
                adm.telegram_id,
                f"📝 <b>Ishchidan yangi mahsulot so'rovi!</b>\n"
                f"Mahsulot: {req.name}\nNarxi: {req.price:,.0f} so'm\n"
                f"Tasdiqlash uchun Mini App -> Admin paneliga kiring.",
                parse_mode="HTML"
            )
        except Exception:
            pass
    return {"status": "pending_approval"}

@app.get("/api/admin/requests")
def get_pending_requests(db: Session = Depends(get_db)):
    return db.query(ProductRequest).filter(ProductRequest.status == "pending").all()

@app.post("/api/admin/requests/{req_id}/{decision}")
def decide_request(req_id: int, decision: str, db: Session = Depends(get_db)):
    req = db.query(ProductRequest).filter(ProductRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="So'rov topilmadi")
    
    if decision == "approve":
        req.status = "approved"
        if req.action == "create":
            prod = Product(
                code=f"W-{random.randint(1000,9999)}",
                name=req.name,
                category_id=req.category_id,
                price=req.price,
                unit=req.unit,
                image_url=req.image_url or "https://placehold.co/300x300/f8f8f8/e52e2e?text=Yangi",
                is_approved=True,
                created_by=req.worker_id
            )
            db.add(prod)
        elif req.action == "update" and req.product_id:
            prod = db.query(Product).filter(Product.id == req.product_id).first()
            if prod:
                prod.name = req.name
                prod.price = req.price
                if req.image_url:
                    prod.image_url = req.image_url
        elif req.action == "delete" and req.product_id:
            db.query(Product).filter(Product.id == req.product_id).delete()
    else:
        req.status = "rejected"
    db.commit()
    return {"status": req.status}

# --- SUPER ADMIN VAKOLATLARNI BOSHQARISH ---

@app.post("/api/superadmin/assign-role")
def assign_role(data: RoleAssign, db: Session = Depends(get_db)):
    admin = db.query(User).filter(User.telegram_id == data.admin_id).first()
    if not admin or admin.role != "super_admin":
        raise HTTPException(status_code=403, detail="Faqat Super Admin rollarni o'zgartira oladi")
    
    target = db.query(User).filter(User.telegram_id == data.target_telegram_id).first()
    if not target:
        target = User(telegram_id=data.target_telegram_id, role=data.role, assigned_category_id=data.category_id)
        db.add(target)
    else:
        target.role = data.role
        target.assigned_category_id = data.category_id
    db.commit()
    return {"status": "ok"}

@app.post("/api/superadmin/settings")
def update_settings(delivery_enabled: bool, free_delivery_min_amount: float = 500000, db: Session = Depends(get_db)):
    s = db.query(StoreSettings).first()
    s.delivery_enabled = delivery_enabled
    s.free_delivery_min_amount = free_delivery_min_amount
    db.commit()
    return s

@app.get("/api/admin/stats")
def get_sales_stats(db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.status != "cancelled").all()
    total_revenue = sum(o.total_amount for o in orders)
    completed = sum(1 for o in orders if o.status == "completed")
    return {
        "total_orders": len(orders),
        "completed_orders": completed,
        "total_revenue": total_revenue
    }

@app.on_event("startup")
async def on_startup():
    init_db()
    db = SessionLocal()
    if db.query(Product).count() == 0 and os.path.exists("tahlil.csv"):
        run_import("tahlil.csv", only_positive_stock=True)
    db.close()
    asyncio.create_task(dp.start_polling(bot))
      
