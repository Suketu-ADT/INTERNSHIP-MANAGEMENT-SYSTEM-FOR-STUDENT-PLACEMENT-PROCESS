import secrets

from sqlalchemy import inspect, text

from database.models import db, User

# Columns added to already-existing tables after the first release.
# db.create_all() only creates missing TABLES, never adds columns to a table
# that already exists - so a column added here must also be listed below to
# reach a database file created before this column existed (SQLite supports
# ADD COLUMN; this is a no-op once the column is present).
_ADDITIVE_COLUMNS = {
    "companies": [("is_demo", "BOOLEAN NOT NULL DEFAULT 0")],
    "internships": [("is_demo", "BOOLEAN NOT NULL DEFAULT 0")],
}


def init_db(app):
    with app.app_context():
        db.create_all()
        _apply_additive_columns()
        _ensure_admin(app)
        if app.config.get("ENABLE_DEMO_SEED"):
            from database.seed_demo import seed_demo_data
            seed_demo_data()


def _apply_additive_columns():
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    for table, columns in _ADDITIVE_COLUMNS.items():
        if table not in existing_tables:
            continue
        existing_columns = {c["name"] for c in inspector.get_columns(table)}
        for column_name, column_def in columns:
            if column_name in existing_columns:
                continue
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_def}"))
    db.session.commit()


def _ensure_admin(app):
    admin_email = app.config["ADMIN_EMAIL"]
    existing = User.query.filter_by(email=admin_email).first()
    if existing:
        return

    password = app.config.get("ADMIN_PASSWORD") or secrets.token_urlsafe(9)
    admin = User(email=admin_email, role="admin")
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()

    if app.config.get("ADMIN_PASSWORD"):
        print(f"[db_init] Created admin account: {admin_email}")
    else:
        print("=" * 64)
        print("[db_init] No ADMIN_PASSWORD was set in .env - generated one:")
        print(f"    Admin email:    {admin_email}")
        print(f"    Admin password: {password}")
        print("Save this now - it will not be shown again. Set ADMIN_PASSWORD")
        print("in .env to choose your own password on the next fresh run.")
        print("=" * 64)
