# Supermarket Telegram Mini App & Bot

Telegram orqali **"Click & Collect" (Buyurtma berish va navbatsiz olib ketish)** hamda ixtiyoriy yetkazib berish tizimiga ega to'liq e-commerce yechim.

## Asosiy imkoniyatlar
- **Rollar tizimi (RBAC):**
  - `Super Admin`: Xodimlar (Admin, Bo'lim ishchisi) qo'shish/o'chirish, yetkazib berish xizmatini yoqish/o'chirish (masalan, 500 000 so'mdan yuqori xaridlarga bepul yetkazish).
  - `Admin`: Buyurtmalarni qabul qilish va holatini boshqarish (`Yangi` -> `Yig'ilmoqda` -> `Tayyor` -> `Topshirildi`), ishchilar yuborgan yangi mahsulotlarni tasdiqlash/rad etish, katalog yaratish/o'chirish, mijozlar bilan chat/rasm orqali muloqot.
  - `Bo'lim ishchisi` (Nonchi, Kolbasachi va h.k.): Faqat o'ziga biriktirilgan bo'limga yangi mahsulot qo'shish so'rovini yuboradi.
  - `Mijoz`: `/start` bosganda telefon raqamini tasdiqlaydi, chegirmalarsiz sof narxlarda savatcha yig'adi, buyurtma ID oladi va botga to'g'ridan-to'g'ri savol yoki rasm yubora oladi.
- **Avtomatik baza importi:** `tahlil.csv` faylidagi qoldig'i bor mahsulotlar ilova birinchi marta ishga tushganda avtomatik ravishda bo'limlarga ajratilib yuklanadi.

## Google Cloud Run'ga joylash
1. Ushbu papkadagi barcha fayllarni GitHub repozitoriysiga yuklang.
2. Google Cloud Console -> **Cloud Run** -> **Create Service** -> GitHub repozitoriyingizni tanlang (`Dockerfile` orqali avtomatik yig'iladi).
3. **Variables & Secrets** bo'limiga quyidagilarni kiriting:
   - `BOT_TOKEN` — `@BotFather` bergan bot tokeni
   - `SUPER_ADMIN_ID` — O'zingizning Telegram ID raqamingiz
   - `WEBAPP_URL` — Cloud Run bergan `https://...run.app` havolasi
   - `DATABASE_URL` — (Tavsiya etiladi) Cloud SQL PostgreSQL ulanish manzili
   
