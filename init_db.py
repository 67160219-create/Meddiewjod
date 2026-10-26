"""สร้างฐานข้อมูล SQLite + ข้อมูลตัวอย่าง (สินค้า 16 รายการ, แอดมิน, ลูกค้าเดโม, ออเดอร์เดโม)
รัน:  python init_db.py   (จะล้างฐานข้อมูลเดิมแล้วสร้างใหม่)"""
import os, sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'customer');
CREATE TABLE addresses(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  address TEXT NOT NULL, is_default INTEGER NOT NULL DEFAULT 0);
CREATE TABLE categories(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE products(id INTEGER PRIMARY KEY, category_id INTEGER NOT NULL REFERENCES categories(id),
  name TEXT NOT NULL, description TEXT, image_url TEXT, price REAL NOT NULL CHECK(price>=0),
  stock INTEGER NOT NULL DEFAULT 0 CHECK(stock>=0), low_stock_threshold INTEGER NOT NULL DEFAULT 5);
CREATE TABLE orders(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'pending', total REAL NOT NULL, shipping_address TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE order_items(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
  product_id INTEGER NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL, unit_price REAL NOT NULL);
"""
CATS = ["วิตามิน", "อาหารเสริม", "สมุนไพร", "ผิวพรรณ"]
# (หมวด 1-4, ชื่อ, คำอธิบาย, ราคา, สต็อก, เกณฑ์สต็อกต่ำ)
PRODUCTS = [
 (1, "วิตามินซี 1000 มก.", "ช่วยเสริมภูมิคุ้มกัน บรรจุ 60 เม็ด", 290, 40, 10),
 (1, "วิตามินดี 3 2000 IU", "บำรุงกระดูกและฟัน บรรจุ 90 เม็ด", 350, 25, 8),
 (1, "วิตามินบีรวม", "ช่วยการเผาผลาญพลังงาน บรรจุ 100 เม็ด", 420, 4, 8),
 (1, "มัลติวิตามิน วิตามินรวมและแร่ธาตุ", "วิตามิน 23 ชนิด บรรจุ 120 เม็ด", 590, 18, 8),
 (2, "น้ำมันปลา โอเมก้า 3", "EPA/DHA สูง บรรจุ 100 แคปซูล", 480, 30, 10),
 (2, "แคลเซียม + แมกนีเซียม", "บำรุงกระดูก บรรจุ 90 เม็ด", 390, 3, 8),
 (2, "โปรไบโอติกส์ 10 สายพันธุ์", "ปรับสมดุลระบบขับถ่าย 30 แคปซูล", 650, 15, 6),
 (2, "คอลลาเจนเปปไทด์ ผงชง", "รสส้ม 30 ซอง", 890, 12, 5),
 (2, "โคเอนไซม์คิวเท็น 100 มก.", "บำรุงหัวใจ บรรจุ 60 แคปซูล", 760, 0, 5),
 (3, "สารสกัดขมิ้นชัน", "ช่วยลดอาการท้องอืด บรรจุ 60 แคปซูล", 220, 50, 10),
 (3, "ฟ้าทะลายโจร", "สมุนไพรไทย บรรจุ 100 แคปซูล", 160, 60, 15),
 (3, "สารสกัดขิง", "ช่วยขับลม บรรจุ 60 แคปซูล", 190, 35, 10),
 (3, "กระชายขาวสกัด", "บรรจุ 60 แคปซูล", 240, 5, 10),
 (4, "ไบโอติน 5000 mcg", "บำรุงผมและเล็บ บรรจุ 90 เม็ด", 450, 22, 8),
 (4, "กลูต้าไธโอน 500 มก.", "บำรุงผิว บรรจุ 30 แคปซูล", 990, 9, 5),
 (4, "เซราไมด์ + วิตามินอี", "บำรุงผิวแห้ง บรรจุ 30 แคปซูล", 720, 14, 5),
]
# ออเดอร์เดโม: (กี่วันก่อน, สถานะ, [(product_id, จำนวน)])
DEMO = [(6,"delivered",[(1,2),(5,1)]),(5,"delivered",[(8,1)]),(4,"shipped",[(4,1),(10,2)]),
        (3,"delivered",[(15,1),(14,1)]),(2,"shipped",[(7,2)]),(1,"pending",[(2,1),(11,3)]),
        (1,"pending",[(16,1)]),(0,"pending",[(5,2),(1,1)]),(0,"cancelled",[(12,1)])]

def init(path):
    if os.path.exists(path): os.remove(path)
    con = sqlite3.connect(path); con.executescript(SCHEMA)
    con.executemany("INSERT INTO categories(name) VALUES(?)", [(c,) for c in CATS])
    con.executemany("INSERT INTO products(category_id,name,description,price,stock,low_stock_threshold) VALUES(?,?,?,?,?,?)", PRODUCTS)
    con.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)", ("ผู้ดูแลร้าน","admin@meddiewjod.shop",generate_password_hash("admin1234"),"admin"))
    con.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)", ("สมชาย ใจดี","customer@example.com",generate_password_hash("customer123"),"customer"))
    addr = "99/1 ถ.สุขุมวิท ต.หนองปรือ อ.บางละมุง จ.ชลบุรี 20150"
    con.execute("INSERT INTO addresses(user_id,address,is_default) VALUES(2,?,1)", (addr,))
    for days, status, items in DEMO:
        rows = [(pid, n, con.execute("SELECT price FROM products WHERE id=?", (pid,)).fetchone()[0]) for pid, n in items]
        ts = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        oid = con.execute("INSERT INTO orders(user_id,status,total,shipping_address,created_at) VALUES(2,?,?,?,?)",
                          (status, sum(n*p for _, n, p in rows), addr, ts)).lastrowid
        con.executemany("INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES(?,?,?,?)", [(oid,)+r for r in rows])
    con.commit(); con.close()

if __name__ == "__main__":
    p = os.environ.get("DATABASE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop.db"))
    init(p); print("สร้างฐานข้อมูลแล้ว:", p)
