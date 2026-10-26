import csv, io, os, sqlite3
from datetime import datetime
from functools import wraps
from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from werkzeug.security import check_password_hash, generate_password_hash
from init_db import init

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("DATABASE", os.path.join(BASE, "shop.db"))
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
if not os.path.exists(DB):
    init(DB)

ST = {"pending": ("รอดำเนินการ", "bg-amber-50 text-amber-700"),
      "shipped": ("จัดส่งแล้ว", "bg-sky-50 text-sky-700"),
      "delivered": ("ส่งถึงแล้ว", "bg-emerald-50 text-emerald-700"),
      "cancelled": ("ยกเลิก", "bg-stone-100 text-stone-500")}

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d: d.close()

def q(sql, args=(), one=False):
    r = db().execute(sql, args).fetchall()
    return (r[0] if r else None) if one else r

now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@app.template_filter("baht")
def baht(v): return f"฿{v:,.0f}"

@app.context_processor
def inject():
    return dict(ST=ST, cart_n=sum(session.get("cart", {}).values()))

# ---------- ล็อกอิน / สิทธิ์ ----------
lm = LoginManager(app)
lm.login_view = "login"
lm.login_message = "กรุณาเข้าสู่ระบบก่อน"

class User(UserMixin):
    def __init__(self, r): self.id, self.name, self.email, self.role = r["id"], r["name"], r["email"], r["role"]

@lm.user_loader
def load_user(uid):
    r = q("SELECT * FROM users WHERE id=?", (uid,), True)
    return User(r) if r else None

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not current_user.is_authenticated: return lm.unauthorized()
        if current_user.role != "admin": abort(403)
        return f(*a, **k)
    return w

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        name, email, pw = f.get("name", "").strip(), f.get("email", "").strip().lower(), f.get("password", "")
        if not name or not email or len(pw) < 6:
            flash("กรอกข้อมูลให้ครบ และรหัสผ่านอย่างน้อย 6 ตัวอักษร", "error")
        elif q("SELECT 1 FROM users WHERE email=?", (email,), True):
            flash("อีเมลนี้ถูกใช้งานแล้ว", "error")
        else:
            uid = db().execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'customer')",
                               (name, email, generate_password_hash(pw))).lastrowid
            db().commit()
            login_user(User(q("SELECT * FROM users WHERE id=?", (uid,), True)))
            flash("สมัครสมาชิกสำเร็จ", "ok")
            return redirect(url_for("index"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        r = q("SELECT * FROM users WHERE email=?", (request.form.get("email", "").strip().lower(),), True)
        if r and check_password_hash(r["password_hash"], request.form.get("password", "")):
            login_user(User(r))
            nxt = request.args.get("next", "")
            if nxt.startswith("/") and not nxt.startswith("//"): return redirect(nxt)
            return redirect(url_for("admin" if r["role"] == "admin" else "index"))
        flash("อีเมลหรือรหัสผ่านไม่ถูกต้อง", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))

# ---------- แคตตาล็อก ----------
@app.route("/")
def index():
    s, c, so = request.args.get("q", "").strip(), request.args.get("cat", type=int), request.args.get("sort", "")
    sql, a = "SELECT p.*, c.name cat FROM products p JOIN categories c ON c.id=p.category_id WHERE 1=1", []
    if s: sql += " AND (p.name LIKE ? OR p.description LIKE ?)"; a += [f"%{s}%"] * 2
    if c: sql += " AND p.category_id=?"; a.append(c)
    sql += {"price_asc": " ORDER BY p.price", "price_desc": " ORDER BY p.price DESC"}.get(so, " ORDER BY p.id")
    return render_template("index.html", products=q(sql, a), cats=q("SELECT * FROM categories"), s=s, c=c, so=so)

@app.route("/product/<int:pid>")
def product(pid):
    p = q("SELECT p.*, c.name cat FROM products p JOIN categories c ON c.id=p.category_id WHERE p.id=?", (pid,), True)
    if not p: abort(404)
    return render_template("product.html", p=p)

# ---------- ตะกร้า / Checkout ----------
def cart_items():
    items, total = [], 0
    for pid, n in session.get("cart", {}).items():
        p = q("SELECT * FROM products WHERE id=?", (pid,), True)
        if p: items.append((p, n, p["price"] * n)); total += p["price"] * n
    return items, total

@app.route("/cart", methods=["GET", "POST"])
def cart():
    if request.method == "POST":
        act, pid = request.form.get("act"), request.form.get("pid", "")
        n = max(request.form.get("qty", 1, type=int), 0)
        p = q("SELECT * FROM products WHERE id=?", (pid,), True)
        c = session.get("cart", {})
        if p and act in ("add", "update"):
            new = c.get(pid, 0) + n if act == "add" else n
            if new > p["stock"]: new = p["stock"]; flash(f"{p['name']} เหลือในสต็อก {p['stock']} ชิ้น", "error")
            elif act == "add": flash("เพิ่มลงตะกร้าแล้ว", "ok")
            if new > 0: c[pid] = new
            else: c.pop(pid, None)
        elif act == "remove": c.pop(pid, None)
        session["cart"] = c
        return redirect(url_for("cart"))
    items, total = cart_items()
    return render_template("cart.html", items=items, total=total)

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items, total = cart_items()
    if not items:
        flash("ตะกร้าว่าง", "error"); return redirect(url_for("cart"))
    if request.method == "POST":
        ship = request.form.get("address", "").strip()
        if not ship:
            flash("กรุณากรอกที่อยู่จัดส่ง", "error"); return redirect(url_for("checkout"))
        con = db()
        try:  # สร้างออเดอร์ + ตัดสต็อกใน transaction เดียว
            for p, n, _ in items:
                if con.execute("UPDATE products SET stock=stock-? WHERE id=? AND stock>=?", (n, p["id"], n)).rowcount == 0:
                    raise ValueError(f"{p['name']} สต็อกไม่พอ")
            oid = con.execute("INSERT INTO orders(user_id,status,total,shipping_address,created_at) VALUES(?,?,?,?,?)",
                              (current_user.id, "pending", total, ship, now())).lastrowid
            con.executemany("INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES(?,?,?,?)",
                            [(oid, p["id"], n, p["price"]) for p, n, _ in items])
            con.commit()
        except ValueError as e:
            con.rollback(); flash(str(e), "error"); return redirect(url_for("cart"))
        session.pop("cart", None)
        flash(f"สั่งซื้อสำเร็จ (จำลองการชำระเงิน) เลขที่ #{oid}", "ok")
        return redirect(url_for("orders"))
    d = q("SELECT address FROM addresses WHERE user_id=? ORDER BY is_default DESC", (current_user.id,))
    return render_template("checkout.html", items=items, total=total, addrs=d)

# ---------- บัญชีลูกค้า ----------
@app.route("/orders")
@login_required
def orders():
    os_ = q("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (current_user.id,))
    items = {o["id"]: q("SELECT oi.*, p.name FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE order_id=?", (o["id"],)) for o in os_}
    return render_template("orders.html", orders=os_, items=items)

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        f, con, uid = request.form, db(), current_user.id
        act, text = f.get("act"), f.get("address", "").strip()
        if act == "name" and f.get("name", "").strip():
            con.execute("UPDATE users SET name=? WHERE id=?", (f["name"].strip(), uid))
        elif act == "add" and text:
            if f.get("is_default"): con.execute("UPDATE addresses SET is_default=0 WHERE user_id=?", (uid,))
            con.execute("INSERT INTO addresses(user_id,address,is_default) VALUES(?,?,?)", (uid, text, 1 if f.get("is_default") else 0))
        elif act == "default":
            con.execute("UPDATE addresses SET is_default=0 WHERE user_id=?", (uid,))
            con.execute("UPDATE addresses SET is_default=1 WHERE id=? AND user_id=?", (f.get("id"), uid))
        elif act == "delete":
            con.execute("DELETE FROM addresses WHERE id=? AND user_id=?", (f.get("id"), uid))
        con.commit(); flash("บันทึกแล้ว", "ok")
        return redirect(url_for("profile"))
    return render_template("profile.html", addrs=q("SELECT * FROM addresses WHERE user_id=? ORDER BY is_default DESC, id", (current_user.id,)),
                           me=q("SELECT * FROM users WHERE id=?", (current_user.id,), True))

# ---------- แอดมิน ----------
@app.route("/admin")
@admin_required
def admin():
    s = q("SELECT COALESCE(SUM(total),0) rev, COUNT(*) n FROM orders WHERE status!='cancelled'", one=True)
    daily = list(reversed(q("SELECT substr(created_at,1,10) d, SUM(total) t FROM orders WHERE status!='cancelled' GROUP BY d ORDER BY d DESC LIMIT 7")))
    return render_template("admin_dashboard.html", s=s, daily=daily, top=max([r["t"] for r in daily] or [1]),
        pending=q("SELECT COUNT(*) n FROM orders WHERE status='pending'", one=True)["n"],
        customers=q("SELECT COUNT(*) n FROM users WHERE role='customer'", one=True)["n"],
        recent=q("SELECT o.*, u.name FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.id DESC LIMIT 6"),
        low=q("SELECT * FROM products WHERE stock<=low_stock_threshold ORDER BY stock, name"))

@app.route("/admin/products", methods=["GET", "POST"])
@admin_required
def admin_products():
    if request.method == "POST":
        f, con, act = request.form, db(), request.form.get("act")
        if act == "delete":
            if q("SELECT 1 FROM order_items WHERE product_id=?", (f.get("id"),), True): flash("ลบไม่ได้: สินค้ามีประวัติการสั่งซื้อ (ตั้งสต็อกเป็น 0 แทน)", "error")
            else: con.execute("DELETE FROM products WHERE id=?", (f.get("id"),)); flash("ลบสินค้าแล้ว", "ok")
        else:
            try:
                v = (int(f["category_id"]), f["name"].strip(), f.get("description", "").strip(), f.get("image_url", "").strip(),
                     float(f["price"]), int(f["stock"]), int(f.get("low_stock_threshold", 5)))
                if not v[1] or v[4] < 0 or v[5] < 0: raise ValueError
                if act == "add": con.execute("INSERT INTO products(category_id,name,description,image_url,price,stock,low_stock_threshold) VALUES(?,?,?,?,?,?,?)", v)
                else: con.execute("UPDATE products SET category_id=?,name=?,description=?,image_url=?,price=?,stock=?,low_stock_threshold=? WHERE id=?", v + (f["id"],))
                flash("บันทึกสินค้าแล้ว", "ok")
            except (ValueError, KeyError):
                flash("ข้อมูลสินค้าไม่ถูกต้อง", "error")
        con.commit()
        return redirect(url_for("admin_products"))
    return render_template("admin_products.html", products=q("SELECT * FROM products ORDER BY id"), cats=q("SELECT * FROM categories"))

ORDER_SQL = """SELECT o.*, u.name, u.email, (SELECT group_concat(p.name||' x'||oi.quantity, ', ') FROM order_items oi
  JOIN products p ON p.id=oi.product_id WHERE oi.order_id=o.id) items FROM orders o JOIN users u ON u.id=o.user_id"""

@app.route("/admin/orders", methods=["GET", "POST"])
@admin_required
def admin_orders():
    if request.method == "POST":
        oid, new = request.form.get("id"), request.form.get("status")
        o = q("SELECT * FROM orders WHERE id=?", (oid,), True)
        if o and new in ST and o["status"] != "cancelled":
            if new == "cancelled":  # คืนสต็อกเมื่อยกเลิก
                for it in q("SELECT * FROM order_items WHERE order_id=?", (oid,)):
                    db().execute("UPDATE products SET stock=stock+? WHERE id=?", (it["quantity"], it["product_id"]))
            db().execute("UPDATE orders SET status=? WHERE id=?", (new, oid)); db().commit()
            flash(f"อัปเดตออเดอร์ #{oid} แล้ว", "ok")
        else:
            flash("ออเดอร์ที่ยกเลิกแล้วเปลี่ยนสถานะไม่ได้", "error")
        return redirect(url_for("admin_orders", status=request.args.get("status", "")))
    st = request.args.get("status", "")
    rows = q(ORDER_SQL + (" WHERE o.status=?" if st in ST else "") + " ORDER BY o.id DESC", (st,) if st in ST else ())
    return render_template("admin_orders.html", orders=rows, st=st)

@app.route("/admin/orders.csv")
@admin_required
def orders_csv():
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["order_id", "created_at", "customer", "email", "status", "total", "items", "shipping_address"])
    for o in q(ORDER_SQL + " ORDER BY o.id DESC"):
        w.writerow([o["id"], o["created_at"], o["name"], o["email"], o["status"], o["total"], o["items"], o["shipping_address"]])
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=orders.csv"})

@app.errorhandler(403)
def forbidden(_): return render_template("error.html", code=403, msg="หน้านี้สำหรับผู้ดูแลร้านเท่านั้น"), 403
@app.errorhandler(404)
def notfound(_): return render_template("error.html", code=404, msg="ไม่พบหน้าที่ต้องการ"), 404

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")