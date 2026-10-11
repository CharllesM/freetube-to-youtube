"""
youtube_sync.py
Gerencia a autenticação OAuth 2.0 e as chamadas da YouTube Data API v3
para criar playlists e adicionar vídeos à conta do usuário.
"""

import json
import os
import sys
import time
from typing import Dict, Any, List, Optional

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build, Resource
    from googleapiclient.errors import HttpError
except ImportError:
    # As bibliotecas do Google são requeridas em tempo de execução
    pass

SCOPES = ["https://www.googleapis.com/auth/youtube"]


class YouTubeSyncService:
    def __init__(
        self,
        credentials_file: str = "credentials.json",
        token_file: str = "token.json",
        state_file: str = "progress.json",
        privacy_status: str = "private",
        request_delay: float = 0.5
    ):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.state_file = state_file
        self.privacy_status = privacy_status
        self.request_delay = request_delay
        self.service: Optional[Resource] = None
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Carrega o progresso salvo para permitir continuar de onde parou."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"created_playlists": {}, "added_videos": {}}

    def _save_state(self):
        """Persiste o progresso salvo em disco."""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"  [Aviso] Falha ao salvar estado de progresso: {e}")

    def authenticate(self) -> Resource:
        """
        Realiza a autenticação OAuth 2.0 do usuário.
        Utiliza token.json em cache ou inicia fluxo de autorização no navegador.
        """
        if "google_auth_oauthlib" not in sys.modules and "googleapiclient" not in sys.modules:
            raise RuntimeError(
                "As bibliotecas da API do Google não estão instaladas.\n"
                "Instale-as executando: pip install -r requirements.txt"
            )

        creds = None
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            except Exception:
                creds = None

        # Se não há credenciais válidas salvas
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("🔄 Renovando token de acesso do YouTube...")
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"\n[ERRO] Arquivo de credenciais não encontrado: '{self.credentials_file}'.\n"
                        "Por favor, acesse o Google Cloud Console, baixe o arquivo de credenciais\n"
                        "OAuth 2.0 (Aplicativo para Computador) e salve como 'credentials.json'.\n"
                        "Consulte o arquivo README.md para o passo a passo completo."
                    )
                print("🌐 Iniciando autenticação OAuth 2.0 no navegador...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Salva credenciais para próximas execuções
            with open(self.token_file, "w", encoding="utf-8") as token_out:
                token_out.write(creds.to_json())
            print("✅ Autenticação realizada com sucesso e salva em token.json.")

        self.service = build("youtube", "v3", credentials=creds)
        return self.service

    def create_playlist(self, title: str, description: str = "") -> Optional[str]:
        """Cria uma nova playlist na conta do usuário no YouTube."""
        if not self.service:
            raise RuntimeError("Serviço YouTube não inicializado. Chame authenticate() primeiro.")

        body = {
            "snippet": {
                "title": title,
                "description": description or f"Restaurada a partir do FreeTube em {time.strftime('%d/%m/%Y')}",
                "defaultLanguage": "pt"
            },
            "status": {
                "privacyStatus": self.privacy_status
            }
        }

        try:
            request = self.service.playlists().insert(
                part="snippet,status",
                body=body
            )
            response = request.execute()
            playlist_id = response.get("id")
            time.sleep(self.request_delay)
            return playlist_id
        except HttpError as err:
            self._handle_http_error(err, context=f"ao criar playlist '{title}'")
            return None

    def add_video_to_playlist(self, playlist_id: str, video_id: str) -> bool:
        """Adiciona um vídeo a uma playlist existente no YouTube."""
        if not self.service:
            raise RuntimeError("Serviço YouTube não inicializado. Chame authenticate() primeiro.")

        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }

        try:
            request = self.service.playlistItems().insert(
                part="snippet",
                body=body
            )
            request.execute()
            time.sleep(self.request_delay)
            return True
        except HttpError as err:
            self._handle_http_error(err, context=f"ao adicionar vídeo ID '{video_id}'")
            return False

    def _handle_http_error(self, err: HttpError, context: str = ""):
        """Trata erros comuns da API do YouTube (cota excedida, vídeo deletado, etc)."""
        status_code = err.resp.status
        try:
            content = json.loads(err.content.decode("utf-8"))
            errors = content.get("error", {}).get("errors", [])
            reason = errors[0].get("reason") if errors else ""
            message = content.get("error", {}).get("message", str(err))
        except Exception:
            reason = ""
            message = str(err)

        if reason == "quotaExceeded" or status_code == 403 and "quota" in message.lower():
            print(f"\n⚠️  [COTA DIÁRIA ATINGIDA] {context}")
            print("A API do YouTube possui uma cota diária gratuita (normalmente 10.000 unidades/dia).")
            print("Cada inserção de playlist ou vídeo consome aproximadamente 50 unidades.")
            print(f"O seu progresso foi salvo em '{self.state_file}'.")
            print("Execute o script novamente amanhã (ou quando a cota resetar à meia-noite PST) para continuar de onde parou!")
            raise QuotaExceededError("Cota diária da API do YouTube excedida.")

        if reason in ("videoNotFound", "invalidVideoId") or status_code == 404:
            print(f"  [Indisponível] Vídeo não encontrado ou removido do YouTube {context}. Pulando...")
            return

        if reason == "forbidden" or status_code == 403:
            print(f"  [Aviso] Vídeo restrito, privado ou com restrição geográfica {context}. Pulando...")
            return

        print(f"  [Erro {status_code}] Falha {context}: {message}")

    def sync_playlists(self, playlists_data: List[Dict[str, Any]], resume: bool = True):
        """
        Sincroniza todas as playlists e seus vídeos com o YouTube.
        """
        total_playlists = len(playlists_data)
        print(f"\n🚀 Iniciando restauração de {total_playlists} playlist(s) para o YouTube...")
        print(f"🔒 Privacidade configurada: '{self.privacy_status}'")

        for idx, pl in enumerate(playlists_data, 1):
            freetube_id = pl["id"]
            name = pl["name"]
            description = pl.get("description", "")
            videos = pl.get("videos", [])

            print(f"\n[{idx}/{total_playlists}] Processando playlist: '{name}' ({len(videos)} vídeos)")

            # Verificar se já foi criada anteriormente (retomada)
            yt_playlist_id = None
            if resume and freetube_id in self.state.get("created_playlists", {}):
                yt_playlist_id = self.state["created_playlists"][freetube_id]
                print(f"  ↪ Playlist já existente no YouTube (ID: {yt_playlist_id}). Retomando inserção de vídeos...")
            else:
                yt_playlist_id = self.create_playlist(name, description)
                if not yt_playlist_id:
                    print(f"  ❌ Não foi possível criar a playlist '{name}'. Pulando para a próxima...")
                    continue
                self.state.setdefault("created_playlists", {})[freetube_id] = yt_playlist_id
                self._save_state()
                print(f"  ✅ Playlist criada com sucesso! (ID: {yt_playlist_id})")

            # Lista de vídeos já adicionados para esta playlist
            added_videos = set(self.state.setdefault("added_videos", {}).setdefault(yt_playlist_id, []))

            # Adicionar vídeos
            for v_idx, v in enumerate(videos, 1):
                vid = v["id"]
                vtitle = v.get("title", "Sem título")

                if resume and vid in added_videos:
                    continue

                print(f"    ({v_idx}/{len(videos)}) Adicionando: {vtitle} [{vid}]...")
                success = self.add_video_to_playlist(yt_playlist_id, vid)
                if success:
                    added_videos.add(vid)
                    self.state["added_videos"][yt_playlist_id] = list(added_videos)
                    self._save_state()

        print("\n🎉 Processo de restauração concluído com sucesso!")


class QuotaExceededError(Exception):
    """Exceção levantada quando a cota diária da API do YouTube é atingida."""
    pass
