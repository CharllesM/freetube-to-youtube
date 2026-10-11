# 📺 FreeTube to YouTube Playlist Restorer

Este projeto permite ler o arquivo de banco de dados (`playlists.db`) do **FreeTube** e restaurar automaticamente todas as suas playlists e vídeos salvos diretamente na sua conta do **YouTube** utilizando a **YouTube Data API v3**.

---

## 🌟 Recursos

- **Suporte nativo ao FreeTube:** Lê perfeitamente a base do FreeTube (formato NeDB / JSON Lines), além de SQLite e JSON.
- **Autenticação OAuth 2.0:** Conexão segura e oficial com a sua conta Google/YouTube com cache local em `token.json`.
- **Controle de Privacidade:** Defina se as playlists serão criadas como `private` (privada - padrão), `unlisted` (não listada) ou `public` (pública).
- **Tratamento Inteligente de Cotas (10.000 unidades/dia):** Se atingir o limite diário da API do YouTube, o estado é gravado em `progress.json`. Você pode rodar no dia seguinte e ele continua exatamente de onde parou sem duplicar vídeos!
- **Tolerância a falhas:** Vídeos deletados ou indisponíveis no YouTube são ignorados sem travar a sincronização das playlists.
- **Modo Simulação (`--dry-run`):** Visualize todas as playlists e vídeos encontrados no arquivo sem realizar nenhuma alteração no YouTube.

---

## 📂 Onde encontrar o arquivo do FreeTube?

No seu computador, o arquivo `playlists.db` geralmente fica em:

- **Linux:** `~/.config/FreeTube/playlists.db`
- **Windows:** `%APPDATA%\FreeTube\playlists.db` (ex: `C:\Users\SeuUsuario\AppData\Roaming\FreeTube\playlists.db`)
- **macOS:** `~/Library/Application Support/FreeTube/playlists.db`

---

## 🔑 Passo a Passo: Configurar a YouTube Data API v3

Para que o script possa criar playlists na sua conta, você precisará de uma credencial OAuth do Google Cloud:

### 1. Criar um projeto no Google Cloud
1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. No menu superior, clique em selecionar projeto e crie um **Novo Projeto** (ex: `FreeTube Sync`).

### 2. Ativar a YouTube Data API v3
1. No menu lateral, vá para **APIs e Serviços** > **Biblioteca**.
2. Pesquise por **YouTube Data API v3**.
3. Clique nela e selecione **Ativar**.

### 3. Configurar a Tela de Permissão OAuth
1. Vá em **APIs e Serviços** > **Tela de permissão OAuth** (OAuth consent screen).
2. Selecione **Externo** (External) e clique em **Criar**.
3. Preencha o nome do app (ex: `FreeTube Sync`) e seu e-mail de contato.
4. Na aba **Escopos**, você pode avançar ou adicionar o escopo `https://www.googleapis.com/auth/youtube`.
5. ⚠️ **Importante (Usuários de teste):** Na etapa de **Usuários de teste** (Test Users), adicione o **mesmo e-mail da sua conta do YouTube** onde as playlists serão restauradas.
6. Salve até o final.

### 4. Criar a Credencial OAuth (Desktop App)
1. Vá em **APIs e Serviços** > **Credenciais**.
2. Clique em **+ Criar Credenciais** > **ID do cliente OAuth**.
3. Em *Tipo de aplicativo*, selecione **Aplicativo para Computador** (Desktop App).
4. Dê um nome (ex: `FreeTube Client`) e clique em **Criar**.
5. Clique no ícone de download (⬇️) para baixar o arquivo JSON.
6. Renomeie o arquivo baixado para `credentials.json` e mova-o para a pasta deste projeto.

---

## 🛠️ Instalação

Certifique-se de ter o Python 3.8+ instalado.

1. Clone ou entre na pasta do projeto:
```bash
cd freetube-to-youtube
```

2. Instale as dependências necessárias:
```bash
pip install -r requirements.txt
```

---

## 🚀 Como Usar

### 1. Testar e Visualizar (Simulação / Dry Run)
Antes de enviar qualquer dado ao YouTube, você pode rodar em modo simulação para conferir as playlists e os vídeos encontrados:

```bash
# Testar com o arquivo de exemplo incluso:
python3 main.py sample_playlists.db --dry-run

# Testar com o seu arquivo real do FreeTube:
python3 main.py caminho/para/seu/playlists.db --dry-run
```

### 2. Restaurar as Playlists no YouTube
Coloque o seu arquivo `credentials.json` na pasta do projeto e execute:

```bash
python3 main.py caminho/para/seu/playlists.db
```
Se apresentar erro e estiver no CMD:
```bash
python main.py caminho/para/seu/playlists.db
```

Na primeira execução:
1. Uma janela do seu navegador será aberta solicitando login na sua conta Google.
2. Autorize o aplicativo.
3. As credenciais de acesso serão salvas localmente em `token.json` para que você não precise autorizar novamente.
4. As playlists começarão a ser criadas e os vídeos inseridos um a um!

---

## ⚙️ Opções e Parâmetros

| Parâmetro | Descrição | Padrão |
|---|---|---|
| `db_file` | Caminho para o arquivo `.db` do FreeTube | `playlists.db` |
| `--credentials`, `-c` | Caminho para o arquivo JSON de credenciais | `credentials.json` |
| `--privacy`, `-p` | Privacidade das playlists: `private`, `unlisted`, `public` | `private` |
| `--dry-run` | Apenas lista os dados encontrados sem alterar o YouTube | Desativado |
| `--delay` | Intervalo em segundos entre cada requisição | `0.5` |
| `--no-resume` | Ignora o progresso anterior em `progress.json` | Desativado |

### Exemplos:

- **Criar playlists como não-listadas:**
  ```bash
  python3 main.py playlists.db --privacy unlisted
  ```

- **Especificar outro caminho para as credenciais:**
  ```bash
  python3 main.py /caminho/playlists.db --credentials /meu/diretorio/meu_segredo.json
  ```

---

## 📊 Limite de Cota da API do YouTube (10.000 unidades/dia)

A API do YouTube impõe um limite gratuito de **10.000 unidades de cota por dia**:
- Criar 1 playlist = **50 unidades**
- Adicionar 1 vídeo = **50 unidades**

Isso permite restaurar cerca de **190 a 200 vídeos por dia**. 

💡 **O que acontece se a cota for atingida?**
O script detecta o erro de cota automaticamente, salva o progresso atual no arquivo `progress.json` e encerra com segurança. No dia seguinte (após a meia-noite no horário do Pacífico - PST), basta rodar o mesmo comando novamente:
```bash
python3 main.py playlists.db
```
No CMD:
```bash
python main.py playlists.db
```
O script identificará as playlists já criadas e continuará exatamente no vídeo onde parou, sem criar duplicatas!

---

## 🧪 Executar Testes Unitários

Para validar os extratores de dados:
```bash
python3 test_extractor.py
```
No CMD:
```bash
python test_extractor.py
```
