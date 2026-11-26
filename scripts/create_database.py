"""Create the database named in DATABASE_URL if the server does not have it yet."""

from sqlalchemy import column, create_engine, make_url, select, table, text

from app.config import Settings

url = make_url(Settings.from_env().database_url)
# Connect to the server's own "postgres" database; CREATE DATABASE cannot run inside a transaction.
engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
with engine.connect() as connection:
    databases = table("pg_database", column("datname"))
    if connection.scalar(select(databases.c.datname).where(databases.c.datname == url.database)):
        print(f"Database {url.database}: already exists")
    else:
        # SQLAlchemy has no builder for CREATE DATABASE; the name is quoted as an identifier.
        connection.execute(text(f"CREATE DATABASE {engine.dialect.identifier_preparer.quote(url.database)}"))
        print(f"Database {url.database}: created")
