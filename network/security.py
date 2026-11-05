import hashlib
import hmac
import json
from pathlib import Path
import secrets
import threading
import time


def password_hash(password,salt=None):
    if len(password)<12:raise ValueError('Use uma senha com pelo menos 12 caracteres.')
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),310000).hex()
    return {'salt':salt,'hash':digest,'iterations':310000}


def add_user(path,username,password,role):
    if role not in ('reader','editor','admin'):raise ValueError('Perfil inválido.')
    if not username.strip() or len(username)>80:raise ValueError('Usuário inválido.')
    path=Path(path); users=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    users[username]={'role':role,**password_hash(password)}
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp'); temporary.write_text(json.dumps(users,indent=2),encoding='utf-8'); temporary.replace(path)


class Auth:
    def __init__(self,path):
        self.path=Path(path); self.sessions={}; self.attempts={}; self.lock=threading.Lock()
        self.dummy=password_hash(secrets.token_urlsafe(24))

    def login(self,username,password,ip):
        with self.lock:
            now=time.monotonic()
            self.attempts={key:[t for t in values if now-t<60] for key,values in self.attempts.items() if any(now-t<60 for t in values)}
            attempts=self.attempts.setdefault(ip,[])
            if len(attempts)>=8:raise ValueError('Muitas tentativas. Aguarde um minuto.')
            attempts.append(now)
        users=json.loads(self.path.read_text(encoding='utf-8'))
        record=users.get(username,self.dummy)
        calculated=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(record['salt']),record.get('iterations',310000)).hex()
        if username not in users or not hmac.compare_digest(calculated,record['hash']):raise ValueError('Usuário ou senha inválidos.')
        token=secrets.token_urlsafe(32)
        with self.lock:
            self.sessions={k:v for k,v in self.sessions.items() if v['expires']>time.time()}
            if len(self.sessions)>=256:raise ValueError('Limite de sessões atingido.')
            self.sessions[hashlib.sha256(token.encode()).hexdigest()]={'username':username,'role':record['role'],'credential':record['hash'],'expires':time.time()+8*3600}
        return token,record['role']

    def verify(self,token):
        with self.lock:record=self.sessions.get(hashlib.sha256(token.encode()).hexdigest())
        if not record or record['expires']<=time.time():return None
        users=json.loads(self.path.read_text(encoding='utf-8'))
        if record['username'] not in users:return None
        if not hmac.compare_digest(record['credential'],users[record['username']]['hash']):return None
        return {**record,'role':users[record['username']]['role']}
