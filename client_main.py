"""Entrada distribuída: exige servidor e nunca cria banco independente."""
import argparse


def main(argv=None):
    parser=argparse.ArgumentParser(description='Cliente de rede do Sistema de Pautas')
    parser.add_argument('--ui',choices=['main','v3'],default='main')
    args=parser.parse_args(argv)
    if args.ui=='v3':
        from ui_v3.app import main as start
    else:
        from main import main as start
    return start(network=True)

if __name__=='__main__':main()
