"""Validação única da configuração privada do servidor, sem tocar no banco."""
import ipaddress
import json
import os
from pathlib import Path
from .media import MediaRoots


def validate_settings(settings,require_users=True):
    settings=dict(settings)
    for key in ('database','backup_directory','users_file','media_roots'):
        if not settings.get(key):raise ValueError('Configuração obrigatória ausente: '+key)
    database=Path(settings['database'])
    if not database.is_absolute() or str(database).startswith('\\\\'):
        raise ValueError('Use um SQLite em disco local do servidor.')
    port=settings.get('port',8000)
    if isinstance(port,bool) or not 1<=int(port)<=65535:raise ValueError('A porta deve estar entre 1 e 65535.')
    settings['port']=int(port)
    if int(settings.get('backup_retention',30))<1:raise ValueError('Retenção de backups deve ser positiva.')
    if int(settings.get('backup_interval_seconds',3600))<60:raise ValueError('Intervalo de backup deve ser de pelo menos 60 segundos.')
    allowed=settings.get('allowed_clients',['127.0.0.1/32','::1/128'])
    if not allowed:raise ValueError('Informe os computadores autorizados.')
    for value in allowed:
        try:network=ipaddress.ip_network(value,strict=False)
        except ValueError:raise ValueError('IP/sub-rede autorizado inválido: '+str(value)) from None
        if network.prefixlen==0 or not network.is_private:raise ValueError('Autorize apenas IPs/sub-redes privadas da rede local.')
    # O assistente testa a API pelo próprio IP LAN do servidor, além do loopback.
    # Autorizar esse único endereço não abre acesso a outros computadores.
    try:
        own=ipaddress.ip_address(settings.get('host','127.0.0.1'))
        own=getattr(own,'ipv4_mapped',None) or own
        if own.is_private and not own.is_unspecified:
            settings['allowed_clients']=list(dict.fromkeys([*allowed,str(own)]))
    except ValueError:pass  # Hostnames podem usar IPs explícitos na lista autorizada.
    media=MediaRoots(settings['media_roots'])
    if os.name=='nt':
        import ctypes
        for value in [settings['database'],*[root['local'] for root in media.roots]]:
            if ctypes.windll.kernel32.GetDriveTypeW(Path(value).anchor)==4:
                raise ValueError('Banco e raízes físicas devem estar em discos locais do servidor, não em unidades de rede mapeadas.')
    for key in ('database','users_file'):
        if media.to_share(str(Path(settings[key]).resolve())):
            raise ValueError('Banco e credenciais devem ficar fora das raízes de mídia compartilhadas.')
    if require_users and not Path(settings['users_file']).is_file():raise ValueError('Cadastre os usuários antes de iniciar o servidor.')
    if bool(settings.get('tls_cert'))!=bool(settings.get('tls_key')):raise ValueError('Configure certificado e chave TLS juntos.')
    return settings


def load_settings(path,require_users=True):
    return validate_settings(json.loads(Path(path).read_text(encoding='utf-8')),require_users)
