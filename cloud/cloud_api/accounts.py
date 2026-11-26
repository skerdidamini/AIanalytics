"""Owner accounts and revocable, server-side sessions."""
import hashlib
import hmac
import secrets
import time

ITERATIONS=600000
SESSION_SECONDS=8*3600
SCHEMA='''
CREATE TABLE IF NOT EXISTS owners (email TEXT PRIMARY KEY,organization_id TEXT NOT NULL,salt TEXT NOT NULL,password_hash TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,
 FOREIGN KEY(organization_id) REFERENCES organizations(id));
CREATE TABLE IF NOT EXISTS account_roles (email TEXT PRIMARY KEY,role TEXT NOT NULL CHECK(role IN ('admin','technician')),FOREIGN KEY(email) REFERENCES owners(email));
CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY,email TEXT NOT NULL,expires REAL NOT NULL,FOREIGN KEY(email) REFERENCES owners(email));
CREATE TABLE IF NOT EXISTS login_attempts (key TEXT NOT NULL,timestamp REAL NOT NULL);
CREATE INDEX IF NOT EXISTS login_attempt_time ON login_attempts(key,timestamp);
'''


def initialize(database):
    connection=database.connect()
    try:
        with connection:connection.executescript(SCHEMA)
    finally:connection.close()


def create_owner(database,organization,email,password,role='reader'):
    if role not in ('reader','admin','technician'):raise ValueError('Invalid account role')
    email=email.strip().casefold()
    if not organization.strip() or len(organization)>128 or len(email)>254 or '@' not in email or len(password)<12 or len(password)>256:
        raise ValueError('Use a valid email and a password of 12–256 characters')
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),ITERATIONS).hex()
    connection=database.connect()
    try:
        with connection:
            connection.execute('INSERT OR IGNORE INTO organizations VALUES (?)',(organization,))
            connection.execute('INSERT INTO owners(email,organization_id,salt,password_hash) VALUES (?,?,?,?)',(email,organization,salt,digest))
            if role!='reader':connection.execute('INSERT INTO account_roles VALUES (?,?)',(email,role))
    finally:connection.close()


class Throttled(Exception):pass


def login(database,email,password,source):
    email=email.strip().casefold()
    now=time.time()
    keys=['email:'+hashlib.sha256(email.encode()).hexdigest(),'source:'+source]
    connection=database.connect()
    try:
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('DELETE FROM login_attempts WHERE timestamp<?',(now-300,))
            for key,limit in zip(keys,[5,20]):
                count=connection.execute('SELECT count(*) FROM login_attempts WHERE key=?',(key,)).fetchone()[0]
                if count>=limit:raise Throttled()
            connection.executemany('INSERT INTO login_attempts VALUES (?,?)',[(key,now) for key in keys])
        owner=connection.execute('SELECT * FROM owners WHERE email=? AND enabled=1',(email,)).fetchone()
        salt=bytes.fromhex(owner['salt']) if owner else bytes(16)
        digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,ITERATIONS).hex()
        if not owner or not hmac.compare_digest(digest,owner['password_hash']):return None
        token=secrets.token_urlsafe(32)
        with connection:
            connection.execute('DELETE FROM login_attempts WHERE key=?',(keys[0],))
            connection.execute('DELETE FROM sessions WHERE expires<?',(now,))
            connection.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),email,now+SESSION_SECONDS))
        return token
    finally:connection.close()


def authenticate(database,token):
    if not token or len(token)>256:return None
    connection=database.connect()
    try:
        owner=connection.execute("SELECT owners.email,organization_id,coalesce(role,'reader') AS role FROM sessions JOIN owners USING(email) LEFT JOIN account_roles USING(email) WHERE digest=? AND expires>? AND enabled=1",
                                 (hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        return {'email':owner['email'],'organization_id':owner['organization_id'],'role':owner['role']} if owner else None
    finally:connection.close()


def logout(database,token):
    connection=database.connect()
    try:
        with connection:connection.execute('DELETE FROM sessions WHERE digest=?',(hashlib.sha256(token.encode()).hexdigest(),))
    finally:connection.close()
