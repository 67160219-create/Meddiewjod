# MedDiewJod Shop

เว็บแอปขายวิตามินและอาหารเสริม (Flask + SQLite + Tailwind) ตามแผนการดำเนินงานโครงการ

## รันในเครื่อง
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python init_db.py        # สร้าง shop.db + ข้อมูลตัวอย่าง (ข้ามได้ ระบบสร้างให้เองถ้ายังไม่มี)
python app.py            # เปิด http://127.0.0.1:5000
```

## บัญชีสำหรับทดลอง
| บทบาท | อีเมล | รหัสผ่าน |
| --- | --- | --- |
| แอดมิน | admin@meddiewjod.shop | admin1234 |
| ลูกค้า | customer@example.com | customer123 |

เปลี่ยนรหัสแอดมินก่อนใช้งานจริง

## ทดสอบ
```bash
python -m unittest discover -s tests -v
```
ครอบคลุม flow หลัก, สต็อกหมด/ตะกร้าว่าง, การบล็อกลูกค้าจากหน้า admin, การคืนสต็อกเมื่อยกเลิก

## Deploy
- ตั้งค่า environment: `SECRET_KEY` (สุ่มค่ายาว ๆ), `DATABASE` (path ไฟล์ SQLite, ถ้าไม่ตั้งใช้ `shop.db`)
- สั่งรัน: `gunicorn app:app` (มี `Procfile` สำหรับ Render/Railway/Heroku)
- SQLite เก็บเป็นไฟล์ ต้องมี persistent disk ไม่งั้นข้อมูลหายเมื่อ redeploy

## โครงสร้าง
```
app.py            routes ทั้งหมด (catalog, cart, checkout, account, admin)
init_db.py        schema + ข้อมูลตัวอย่าง
templates/        หน้า HTML ตามหัวข้อ 4 ของแผน
static/style.css  ฟอนต์ + @media print
tests/            ชุดทดสอบ
```

## สถานะเทียบกับแผน
ทำแล้ว: 6 ฟีเจอร์หลัก, กราฟแท่ง CSS ล้วน, sort ราคา, ป้ายสถานะสี, CSV export, ปุ่มพิมพ์ใบสั่งซื้อ, flash message, คืนสต็อกเมื่อยกเลิก
ยังไม่ทำ: รูปสินค้าจริง (ตอนนี้ใช้ไอคอนแทน หรือใส่ `image_url` ในหน้าจัดการสินค้า), การชำระเงินจริง
หมายเหตุ: แผนระบุ "PHPMySQL" แต่หัวข้อ 4 ใช้ Flask + SQLite จึงทำตามอย่างหลัง
