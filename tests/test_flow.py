"""ทดสอบตามแผนหัวข้อ 7: flow หลัก, กรณีขอบ, และการบล็อกหน้า admin
รัน: python -m unittest discover -s tests -v"""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE"] = os.path.join(tempfile.mkdtemp(), "test.db")
import app as shop

def _all(t):
    with shop.app.app_context(): return [dict(r) for r in shop.q(f"SELECT * FROM {t}")]
def _stock(pid):
    with shop.app.app_context(): return shop.q("SELECT stock FROM products WHERE id=?", (pid,), True)[0]

class Flow(unittest.TestCase):
    def setUp(self):
        shop.init(shop.DB); self.c = shop.app.test_client()
    def login(self, e, p): return self.c.post("/login", data={"email": e, "password": p}, follow_redirects=True)

    def test_main_flow(self):
        self.c.post("/register", data={"name": "ทดสอบ", "email": "t@t.com", "password": "secret1"})
        self.c.post("/cart", data={"act": "add", "pid": "1", "qty": "2"})
        r = self.c.post("/checkout", data={"address": "กรุงเทพ"}, follow_redirects=True)
        self.assertIn("สั่งซื้อสำเร็จ", r.get_data(as_text=True))
        self.assertEqual(_stock(1), 38)
        self.c.get("/logout"); self.login("admin@meddiewjod.shop", "admin1234")
        oid = max(o["id"] for o in _all("orders"))
        self.c.post("/admin/orders", data={"id": oid, "status": "shipped"})
        self.c.get("/logout"); self.login("t@t.com", "secret1")
        self.assertIn("จัดส่งแล้ว", self.c.get("/orders").get_data(as_text=True))

    def test_out_of_stock_and_empty_cart(self):
        self.login("customer@example.com", "customer123")
        self.assertEqual(self.c.get("/checkout").status_code, 302)           # ตะกร้าว่าง
        self.c.post("/cart", data={"act": "add", "pid": "9", "qty": "1"})    # สินค้าสต็อก 0
        with self.c.session_transaction() as s: self.assertFalse(s.get("cart"))

    def test_customer_blocked_from_admin(self):
        self.login("customer@example.com", "customer123")
        for u in ("/admin", "/admin/products", "/admin/orders", "/admin/orders.csv"):
            self.assertEqual(self.c.get(u).status_code, 403, u)

    def test_cancel_restores_stock_and_dashboard(self):
        self.login("admin@meddiewjod.shop", "admin1234")
        for u in ("/admin", "/admin/products", "/admin/orders", "/admin/orders.csv", "/", "/product/1"):
            self.assertEqual(self.c.get(u).status_code, 200, u)
        before = _stock(1); self.c.post("/admin/orders", data={"id": 1, "status": "cancelled"})
        self.assertEqual(_stock(1), before + 2)

if __name__ == "__main__": unittest.main()
