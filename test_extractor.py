"""
test_extractor.py - Testes unitários para freetube_extractor.py
"""

import json
import os
import sqlite3
import tempfile
import unittest
from freetube_extractor import extract_video_id, load_freetube_playlists


class TestFreeTubeExtractor(unittest.TestCase):

    def test_extract_video_id(self):
        # ID simples de 11 caracteres
        self.assertEqual(extract_video_id("hsnZSD4jQhk"), "hsnZSD4jQhk")

        # URL padrão
        self.assertEqual(extract_video_id("https://www.youtube.com/watch?v=hsnZSD4jQhk"), "hsnZSD4jQhk")

        # URL curta
        self.assertEqual(extract_video_id("https://youtu.be/hsnZSD4jQhk"), "hsnZSD4jQhk")

        # URL Shorts
        self.assertEqual(extract_video_id("https://www.youtube.com/shorts/hsnZSD4jQhk"), "hsnZSD4jQhk")

        # Dicionário FreeTube com videoId
        self.assertEqual(extract_video_id({"videoId": "hsnZSD4jQhk", "title": "Never Gonna Give You Up"}), "hsnZSD4jQhk")

        # Dicionário com id
        self.assertEqual(extract_video_id({"id": "hsnZSD4jQhk"}), "hsnZSD4jQhk")

        # Inválido
        self.assertIsNone(extract_video_id("invalido"))
        self.assertIsNone(extract_video_id(None))

    def test_parse_nedb_basic_and_deletions(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".db", delete=False) as f:
            # Doc 1
            f.write(json.dumps({
                "_id": "pl1",
                "name": "Rock Clássico",
                "description": "Melhores rocks",
                "videos": [
                    {"videoId": "hsnZSD4jQhk", "title": "Video 1"},
                    {"videoId": "pSh7uBuvCbU", "title": "Video 2"}
                ]
            }) + "\n")
            # Doc 2 (será deletado)
            f.write(json.dumps({
                "_id": "pl2",
                "name": "Para Deletar",
                "videos": [{"videoId": "kJQP7kiw5Fk"}]
            }) + "\n")
            # Deleção do Doc 2
            f.write(json.dumps({
                "_id": "pl2",
                "$$deleted": True
            }) + "\n")
            # Atualização do Doc 1 adicionando mais um vídeo
            f.write(json.dumps({
                "_id": "pl1",
                "name": "Rock Clássico (Atualizado)",
                "description": "Melhores rocks de todos os tempos",
                "videos": [
                    {"videoId": "hsnZSD4jQhk", "title": "Video 1"},
                    {"videoId": "pSh7uBuvCbU", "title": "Video 2"},
                    {"videoId": "Wl7SjPkAl1Y", "title": "Video 3"}
                ]
            }) + "\n")
            temp_path = f.name

        try:
            playlists = load_freetube_playlists(temp_path)
            self.assertEqual(len(playlists), 1)
            pl = playlists[0]
            self.assertEqual(pl["id"], "pl1")
            self.assertEqual(pl["name"], "Overcomplex - O melhor do Psytrance")
            self.assertEqual(pl["description"], "Melhor psytrance de todos os tempos")
            self.assertEqual(len(pl["videos"]), 3)
            self.assertEqual(pl["videos"][0]["id"], "hsnZSD4jQhk")
            self.assertEqual(pl["videos"][1]["id"], "pSh7uBuvCbU")
            self.assertEqual(pl["videos"][2]["id"], "Wl7SjPkAl1Y")
        finally:
            os.remove(temp_path)

    def test_parse_sqlite(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_path = f.name

        conn = sqlite3.connect(temp_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE playlists (id TEXT PRIMARY KEY, name TEXT, description TEXT)")
        cur.execute("CREATE TABLE playlist_videos (playlist_id TEXT, video_id TEXT, title TEXT)")
        cur.execute("INSERT INTO playlists VALUES ('sq1', 'Minha Playlist SQLite', 'Criada em SQLite')")
        cur.execute("INSERT INTO playlist_videos VALUES ('sq1', 'hsnZSD4jQhk', 'Musica Teste')")
        conn.commit()
        conn.close()

        try:
            playlists = load_freetube_playlists(temp_path)
            self.assertEqual(len(playlists), 1)
            self.assertEqual(playlists[0]["name"], "Minha Playlist SQLite")
            self.assertEqual(len(playlists[0]["videos"]), 1)
            self.assertEqual(playlists[0]["videos"][0]["id"], "hsnZSD4jQhk")
        finally:
            os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
