"""
Seed data for local testing — creates one user per role, a couple of
sample products and scans, and registers the current rules JSON as the
active RuleVersion. Safe to re-run: it skips anything that already
exists instead of erroring or duplicating rows.

Usage:
    cd backend
    python -m app.seed
"""
from .auth import hash_password
from .database import Base, SessionLocal, engine
from . import models
from .routers.rule_versions import _hash_rules_file

SEED_USERS = [
    {"email": "inspector@metrology.gov.in", "full_name": "Asha Verma", "password": "inspector123", "role": models.UserRole.INSPECTOR},
    {"email": "supervisor@metrology.gov.in", "full_name": "Rohit Menon", "password": "supervisor123", "role": models.UserRole.SUPERVISOR},
    {"email": "admin@metrology.gov.in", "full_name": "Dept Admin", "password": "admin123", "role": models.UserRole.ADMIN},
]

SEED_PRODUCTS = [
    {"name": "Refined Sunflower Oil 1L", "brand": "SunGold", "category": "Edible Oil", "manufacturer_name": "SunGold Agro Pvt Ltd"},
    {"name": "Basmati Rice 5kg", "brand": "Daawat", "category": "Staples", "manufacturer_name": "LT Foods Ltd"},
    {"name": "Instant Noodles 70g", "brand": "TastyMax", "category": "Packaged Food", "manufacturer_name": "TastyMax Foods Pvt Ltd"},
    # Exercises the Step 5 country-of-origin conditional rule (R6-1-a-origin).
    {
        "name": "Extra Virgin Olive Oil 500ml",
        "brand": "OlioBella",
        "category": "Edible Oil",
        "manufacturer_name": "OlioBella S.p.A.",
        "is_imported": True,
    },
    # Exercises the Step 5 molded-declaration 2mm threshold (R7-3-molded-height).
    {
        "name": "Carbonated Soft Drink 300ml Glass Bottle",
        "brand": "FizzPop",
        "category": "Beverages",
        "manufacturer_name": "FizzPop Beverages Pvt Ltd",
        "surface_treatment": "molded",
    },
]


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("Seeding users...")
        users_by_email = {}
        for u in SEED_USERS:
            existing = db.query(models.User).filter(models.User.email == u["email"]).first()
            if existing:
                users_by_email[u["email"]] = existing
                print(f"  - {u['email']} already exists, skipping")
                continue
            user = models.User(
                email=u["email"],
                full_name=u["full_name"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
            )
            db.add(user)
            db.flush()
            users_by_email[u["email"]] = user
            print(f"  - created {u['email']} ({u['role'].value}) / password: {u['password']}")
        db.commit()

        print("Registering active rule version from rules/legal_metrology_rules.json...")
        version_label, file_hash = _hash_rules_file()
        rule_version = db.query(models.RuleVersion).filter(models.RuleVersion.source_file_hash == file_hash).first()
        if not rule_version:
            db.query(models.RuleVersion).update({models.RuleVersion.is_active: False})
            rule_version = models.RuleVersion(version_label=version_label, source_file_hash=file_hash, is_active=True)
            db.add(rule_version)
            db.flush()
            print(f"  - registered {version_label} ({file_hash[:12]}...) as active")
        else:
            print(f"  - {version_label} already registered")
        db.commit()

        print("Seeding sample products...")
        inspector = users_by_email["inspector@metrology.gov.in"]
        for p in SEED_PRODUCTS:
            existing = db.query(models.Product).filter(models.Product.name == p["name"]).first()
            if existing:
                print(f"  - {p['name']} already exists, skipping")
                continue
            product = models.Product(**p)
            db.add(product)
            db.flush()
            print(f"  - created product {p['name']}")

            # Give the first product a sample scan (no image, so it just
            # sits in PENDING) to have something non-empty for `GET /scans`.
            existing_scan = db.query(models.Scan).filter(models.Scan.product_id == product.id).first()
            if not existing_scan:
                scan = models.Scan(
                    product_id=product.id,
                    created_by_id=inspector.id,
                    status=models.ScanStatus.PENDING,
                    rule_version_id=rule_version.id,
                )
                db.add(scan)
        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
