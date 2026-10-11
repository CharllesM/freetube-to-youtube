#!/usr/bin/env python3
"""
FreeTube to YouTube Playlist Restorer
Restaura playlists do FreeTube (.db) para a sua conta do YouTube via YouTube Data API v3.
"""

import argparse
import sys
import os
from freetube_extractor import load_freetube_playlists


def print_banner():
    banner = """
=============================================================
  📺 FreeTube to YouTube Data API v3 - Playlist Restorer
=============================================================
    """
    print(banner)


def preview_playlists(playlists):
    total_videos = sum(len(p.get("videos", [])) for p in playlists)
    print(f"\n📁 Encontradas {len(playlists)} playlist(s) com um total de {total_videos} vídeo(s):\n")
    for i, pl in enumerate(playlists, 1):
        print(f"  {i}. {pl['name']} ({len(pl['videos'])} vídeos)")
        if pl.get("description"):
            print(f"     Descrição: {pl['description']}")
        # Mostrar até 3 exemplos de vídeos
        for v in pl['videos'][:3]:
            print(f"      - [{v['id']}] {v.get('title', 'Vídeo')}")
        if len(pl['videos']) > 3:
            print(f"      ... e mais {len(pl['videos']) - 3} vídeo(s)")
        print()


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="Restaura playlists do FreeTube (.db) para sua conta do YouTube."
    )
    parser.add_argument(
        "db_file",
        nargs="?",
        default="playlists.db",
        help="Caminho para o arquivo .db do FreeTube (padrão: playlists.db)"
    )
    parser.add_argument(
        "--credentials",
        "-c",
        default="credentials.json",
        help="Caminho para o arquivo credentials.json baixado do Google Cloud Console (padrão: credentials.json)"
    )
    parser.add_argument(
        "--privacy",
        "-p",
        choices=["private", "unlisted", "public"],
        default="private",
        help="Nível de privacidade das playlists criadas (padrão: private)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas lê e lista o conteúdo do arquivo .db sem interagir com o YouTube"
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignora o histórico de progresso salvo e tenta sincronizar tudo do início"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Tempo de espera (em segundos) entre requisições da API para evitar bloqueios (padrão: 0.5s)"
    )

    args = parser.parse_args()

    # 1. Carregar e validar o arquivo .db
    if not os.path.exists(args.db_file):
        print(f"❌ [ERRO] O arquivo '{args.db_file}' não foi encontrado.")
        print("Uso: python3 main.py <caminho_para_playlists.db>")
        print("Dica: você pode testar com o arquivo de exemplo: python3 main.py sample_playlists.db --dry-run")
        sys.exit(1)

    print(f"🔍 Lendo arquivo do FreeTube: '{args.db_file}'...")
    try:
        playlists = load_freetube_playlists(args.db_file)
    except Exception as e:
        print(f"❌ Falha ao ler o arquivo .db: {e}")
        sys.exit(1)

    if not playlists:
        print("⚠️ Nenhuma playlist encontrada no arquivo fornecido.")
        sys.exit(0)

    # 2. Exibir prévia
    preview_playlists(playlists)

    # Se for apenas simulação (dry-run), encerra aqui
    if args.dry_run:
        print("ℹ️ Modo --dry-run ativo: nenhuma alteração foi enviada para o YouTube.")
        sys.exit(0)

    # 3. Autenticação e Sincronização com o YouTube
    try:
        from youtube_sync import YouTubeSyncService, QuotaExceededError
    except ImportError as e:
        print(f"❌ Dependências ausentes: {e}")
        print("Execute: pip install -r requirements.txt")
        sys.exit(1)

    sync_service = YouTubeSyncService(
        credentials_file=args.credentials,
        privacy_status=args.privacy,
        request_delay=args.delay
    )

    try:
        sync_service.authenticate()
        sync_service.sync_playlists(playlists, resume=not args.no_resume)
    except QuotaExceededError:
        print("\n⚠️ A execução foi pausada devido ao limite de cota diária do YouTube.")
        print("O progresso foi salvo. Rode novamente amanhã para continuar de onde parou.")
        sys.exit(2)
    except Exception as e:
        print(f"\n❌ Ocorreu um erro durante o processo: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
