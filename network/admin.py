"""Administração local do servidor; senhas lidas pelo terminal/entrada padrão."""
import argparse
import getpass
import json
from pathlib import Path
import sys
from .backup import backup_database,restore_database
from .security import add_user
from .media import MediaRoots
from .instance import exclusive_instance
from .configuration import load_settings,validate_settings
from .diagnostics import inspect_environment


def main(argv=None):
    parser=argparse.ArgumentParser()
    commands=parser.add_subparsers(dest='command',required=True)
    init=commands.add_parser('init')
    init.add_argument('--config',required=True); init.add_argument('--database',required=True)
    init.add_argument('--backup-directory',required=True); init.add_argument('--host',default='127.0.0.1'); init.add_argument('--port',type=int,default=8000)
    init.add_argument('--media',action='append',required=True,help='diretório local=compartilhamento UNC')
    init.add_argument('--allow',action='append',default=[])
    for name in ['user','backup','restore','check']:
        sub=commands.add_parser(name); sub.add_argument('--config',required=True)
        if name=='user':
            sub.add_argument('--username',required=True); sub.add_argument('--role',choices=['reader','editor','admin'],required=True); sub.add_argument('--password-stdin',action='store_true')
        if name=='restore':sub.add_argument('--source',required=True); sub.add_argument('--confirm-service-stopped',action='store_true',required=True)
        if name=='check':sub.add_argument('--strict',action='store_true')
    args=parser.parse_args(argv); path=Path(args.config).resolve()
    if args.command=='init':
        if path.exists():raise ValueError('A configuração existente não será sobrescrita.')
        if not Path(args.database).is_absolute() or args.database.startswith('\\\\'):raise ValueError('Use um banco em disco local do servidor.')
        roots=[]
        for entry in args.media:
            local,share=entry.split('=',1); roots.append(dict(id=f'media_{len(roots)+1}',name=Path(local).name or local,local=str(Path(local).resolve()),share=share))
        MediaRoots(roots)
        settings=dict(database=str(Path(args.database).resolve()),backup_directory=str(Path(args.backup_directory).resolve()),
                      users_file=str(path.parent/'users.json'),host=args.host,port=args.port,media_roots=roots,
                      allowed_clients=['127.0.0.1/32','::1/128',*args.allow],backup_interval_seconds=3600,backup_retention=30,wal=True)
        validate_settings(settings,require_users=False)
        path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Configuração criada. O banco existente não foi alterado. Cadastre usuários antes de iniciar.')
        return
    settings=load_settings(path,require_users=args.command!='user')
    if args.command=='user':
        password=sys.stdin.buffer.readline().decode('utf-8').rstrip('\r\n') if args.password_stdin else getpass.getpass('Senha (mínimo 12 caracteres): ')
        add_user(settings['users_file'],args.username,password,args.role); print('Usuário configurado.')
    elif args.command=='check':
        report=inspect_environment(settings,integrity=True)
        print(json.dumps(report,ensure_ascii=False,indent=2))
        if report['database'] not in ('available','new') or (args.strict and any(r['state']!='available' for r in report['media'])):
            raise ValueError('Verificação não aprovada. Corrija o banco/acesso às mídias antes de instalar.')
    elif args.command=='backup':print(backup_database(settings['database'],settings['backup_directory'],settings.get('backup_retention',30)))
    else:
        with exclusive_instance(settings['database']):restore_database(args.source,settings['database'])
        print('Backup restaurado. Cópia anterior preservada no diretório antes-restauracao.')


if __name__=='__main__':main()
