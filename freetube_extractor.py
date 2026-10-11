"""
freetube_extractor.py
Extrai playlists e vídeos de arquivos de banco de dados (.db) do FreeTube.
Suporta formato NeDB (JSON Lines, padrão do FreeTube), SQLite e JSON convencional.
"""

import json
import os
import re
import sqlite3
from typing import List, Dict, Any, Optional

YOUTUBE_VIDEO_ID_REGEX = re.compile(r'^[a-zA-Z0-9_-]{11}$')
YOUTUBE_URL_REGEX = re.compile(
    r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
)


def extract_video_id(item: Any) -> Optional[str]:
    """
    Extrai o ID do vídeo do YouTube a partir de string ou dicionário de vídeo do FreeTube.
    """
    if not item:
        return None

    candidate = None
    if isinstance(item, str):
        candidate = item.strip()
    elif isinstance(item, dict):
        candidate = (
            item.get("videoId")
            or item.get("video_id")
            or item.get("id")
            or item.get("url")
        )
        if isinstance(candidate, dict):
            candidate = candidate.get("videoId") or candidate.get("id")

    if not candidate or not isinstance(candidate, str):
        return None

    candidate = candidate.strip()

    # Se já for um ID de 11 caracteres
    if YOUTUBE_VIDEO_ID_REGEX.match(candidate):
        return candidate

    # Se for uma URL completa do YouTube
    match = YOUTUBE_URL_REGEX.search(candidate)
    if match:
        return match.group(1)

    return None


def extract_video_title(item: Any) -> str:
    """Extrai o título do vídeo para exibição de logs amigáveis."""
    if isinstance(item, dict):
        return item.get("title") or item.get("name") or "Sem título"
    return "Vídeo"


def parse_nedb(filepath: str) -> List[Dict[str, Any]]:
    """
    Parseia arquivo no formato NeDB (JSON Lines com histórico de operações e compactação).
    O FreeTube armazena playlists.db neste formato.
    """
    docs_by_id: Dict[str, Dict[str, Any]] = {}
    line_number = 0

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line_number += 1
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # Pode haver linhas corrompidas ou truncadas
                continue

            if not isinstance(data, dict):
                continue

            doc_id = data.get("_id")
            if not doc_id:
                # Pode ser um documento sem _id
                doc_id = f"anon_{line_number}"

            # Documento marcado como deletado no NeDB
            if data.get("$$deleted") is True:
                docs_by_id.pop(doc_id, None)
                continue

            # Atualização parcial ($set)
            if "$set" in data and doc_id in docs_by_id:
                docs_by_id[doc_id].update(data["$set"])
            else:
                docs_by_id[doc_id] = data

    playlists = []
    for doc_id, doc in docs_by_id.items():
        name = doc.get("name") or doc.get("title") or doc.get("playlistName")
        if not name:
            # Pode ser um metadado interno ou documento não-playlist
            continue

        raw_videos = doc.get("videos") or []
        if not isinstance(raw_videos, list):
            raw_videos = []

        parsed_videos = []
        seen_videos = set()
        for v in raw_videos:
            vid = extract_video_id(v)
            if vid and vid not in seen_videos:
                seen_videos.add(vid)
                parsed_videos.append({
                    "id": vid,
                    "title": extract_video_title(v)
                })

        playlists.append({
            "id": str(doc_id),
            "name": str(name).strip(),
            "description": str(doc.get("description") or doc.get("desc") or "").strip(),
            "videos": parsed_videos
        })

    return playlists


def parse_sqlite(filepath: str) -> List[Dict[str, Any]]:
    """
    Parseia banco de dados SQLite caso o usuário tenha um .db gerado nesse formato.
    """
    conn = sqlite3.connect(filepath)
    cursor = conn.cursor()

    # Localizar tabelas existentes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    playlists = []

    # Tenta padrão 1: Tabela playlists e tabela playlist_videos
    if "playlists" in tables:
        cursor.execute("PRAGMA table_info(playlists)")
        cols = [c[1].lower() for c in cursor.fetchall()]
        id_col = "id" if "id" in cols else cols[0]
        name_col = "name" if "name" in cols else ("title" if "title" in cols else cols[1])
        desc_col = "description" if "description" in cols else None

        select_cols = f"{id_col}, {name_col}" + (f", {desc_col}" if desc_col else "")
        cursor.execute(f"SELECT {select_cols} FROM playlists")
        rows = cursor.fetchall()

        for row in rows:
            pl_id = str(row[0])
            pl_name = str(row[1])
            pl_desc = str(row[2]) if desc_col and len(row) > 2 and row[2] else ""

            videos = []
            # Buscar vídeos vinculados se houver tabela de relacionamento
            for vtable in ["playlist_videos", "videos", "items"]:
                if vtable in tables:
                    cursor.execute(f"PRAGMA table_info({vtable})")
                    vcols = [c[1].lower() for c in cursor.fetchall()]
                    if "playlist_id" in vcols or "playlistid" in vcols:
                        pl_fk = "playlist_id" if "playlist_id" in vcols else "playlistid"
                        vid_col = "video_id" if "video_id" in vcols else ("videoid" if "videoid" in vcols else "id")
                        vtitle_col = "title" if "title" in vcols else None

                        q = f"SELECT {vid_col}" + (f", {vtitle_col}" if vtitle_col else "") + f" FROM {vtable} WHERE {pl_fk} = ?"
                        cursor.execute(q, (pl_id,))
                        for vrow in cursor.fetchall():
                            vid = extract_video_id(vrow[0])
                            if vid:
                                videos.append({
                                    "id": vid,
                                    "title": vrow[1] if vtitle_col and len(vrow) > 1 and vrow[1] else "Vídeo"
                                })
                        break

            playlists.append({
                "id": pl_id,
                "name": pl_name,
                "description": pl_desc,
                "videos": videos
            })

    conn.close()
    return playlists


def parse_json_fallback(filepath: str) -> List[Dict[str, Any]]:
    """Tenta ler como arquivo JSON convencional caso o arquivo não seja NeDB nem SQLite."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("playlists") or data.get("items") or [data]

    playlists = []
    for doc in items:
        if not isinstance(doc, dict):
            continue
        name = doc.get("name") or doc.get("title")
        if not name:
            continue
        raw_videos = doc.get("videos") or []
        videos = []
        for v in raw_videos:
            vid = extract_video_id(v)
            if vid:
                videos.append({
                    "id": vid,
                    "title": extract_video_title(v)
                })
        playlists.append({
            "id": str(doc.get("_id") or doc.get("id") or name),
            "name": str(name),
            "description": str(doc.get("description") or ""),
            "videos": videos
        })
    return playlists


def load_freetube_playlists(filepath: str) -> List[Dict[str, Any]]:
    """
    Função principal de carregamento. Identifica o formato do arquivo .db
    e retorna lista padronizada de playlists com seus respectivos vídeos.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")

    if os.path.getsize(filepath) == 0:
        raise ValueError(f"O arquivo está vazio: {filepath}")

    # Verificar se é SQLite lendo cabeçalho
    with open(filepath, "rb") as f:
        header = f.read(16)
        if header.startswith(b"SQLite format 3"):
            return parse_sqlite(filepath)

    # FreeTube usa NeDB por padrão (linhas de JSON)
    try:
        playlists = parse_nedb(filepath)
        if playlists:
            return playlists
    except Exception:
        pass

    # Fallback para JSON padrão
    try:
        playlists = parse_json_fallback(filepath)
        if playlists:
            return playlists
    except Exception:
        pass

    raise ValueError(
        f"Não foi possível extrair playlists válidas do arquivo '{filepath}'. "
        "Certifique-se de que o arquivo é o 'playlists.db' do FreeTube."
    )
