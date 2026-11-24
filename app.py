import os, json, io, logging, hmac
import base64
from functools import wraps
from flask import Flask, jsonify, render_template, request, Response
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceExistsError
load_dotenv()
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def protect(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        password = os.getenv('APP_PASSWORD', '')
        auth = request.authorization
        if not password or not auth or not hmac.compare_digest(auth.username or '', 'admin') or not hmac.compare_digest(auth.password or '', password):
            return Response('Autenticacao necessaria. Configure APP_PASSWORD.', 401, {'WWW-Authenticate': 'Basic realm="CloudTransfer"'})
        return fn(*args, **kwargs)
    return wrapped

def drive():
    scopes = [
        'https://www.googleapis.com/auth/drive.readonly'
    ]

    raw_base64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')
    raw_json = os.getenv('GOOGLE_CREDENTIALS_JSON')

    if raw_base64:
        print("[GOOGLE] Utilizando credenciais Base64")

        info = json.loads(
            base64.b64decode(raw_base64).decode('utf-8')
        )

        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=scopes
        )

    elif raw_json:
        print("[GOOGLE] Utilizando credenciais JSON")

        creds = service_account.Credentials.from_service_account_info(
            json.loads(raw_json),
            scopes=scopes
        )

    else:
        print("[GOOGLE] Utilizando arquivo local")

        creds = service_account.Credentials.from_service_account_file(
            os.getenv(
                'GOOGLE_APPLICATION_CREDENTIALS',
                'credentials.json'
            ),
            scopes=scopes
        )

    print("[GOOGLE] Credenciais carregadas")

    client = build(
        'drive',
        'v3',
        credentials=creds,
        cache_discovery=False
    )

    print("[GOOGLE] Cliente criado")

    return client
# def drive():
#     scopes = ['https://www.googleapis.com/auth/drive.readonly']
#     raw = os.getenv('GOOGLE_CREDENTIALS_JSON')
#     creds = service_account.Credentials.from_service_account_info(json.loads(raw), scopes=scopes) if raw else service_account.Credentials.from_service_account_file(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], scopes=scopes)
#     return build('drive', 'v3', credentials=creds, cache_discovery=False)

# def container():
#     return BlobServiceClient.from_connection_string(os.environ['AZURE_STORAGE_CONNECTION_STRING']).get_container_client(os.environ['AZURE_CONTAINER_NAME'])

def container():

    connection_string = os.environ[
        'AZURE_STORAGE_CONNECTION_STRING'
    ]

    container_name = os.environ[
        'AZURE_CONTAINER_NAME'
    ].strip()

    service = BlobServiceClient.from_connection_string(
        connection_string
    )

    container_client = service.get_container_client(
        container_name
    )

    try:
        print(f"[INFO] Verificando container: {container_name}")

        if not container_client.exists():

            container_client.create_container()

            print(
                f"[SUCESSO] Container '{container_name}' criado."
            )

        else:
            print(
                f"[INFO] Container '{container_name}' ja existe."
            )

    except ResourceExistsError:
        print(f"[INFO] Container '{container_name}' ja existe.")

    except Exception as e:
        print(f"[ERRO] Tipo: {type(e).__name__}")
        print(f"[ERRO] Detalhes: {e}")
        raise

    return container_client

def list_source(client):
    folder = os.environ['GOOGLE_DRIVE_FOLDER_ID']
    if not all(c.isalnum() or c in '-_' for c in folder):
        raise ValueError('ID de pasta invalido')
    files, token = [], None
    while True:
        result = client.files().list(q=f"'{folder}' in parents and trashed = false and mimeType != 'application/vnd.google-apps.folder'", fields='nextPageToken, files(id,name,mimeType,size)', pageSize=100, pageToken=token).execute()
        files.extend(result.get('files', []))
        token = result.get('nextPageToken')
        if not token: return files

def list_destination(client):
    return [{'name': b.name, 'size': b.size} for b in client.list_blobs()]

EXPORTS = {'application/vnd.google-apps.document': ('application/pdf', '.pdf'), 'application/vnd.google-apps.spreadsheet': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'), 'application/vnd.google-apps.presentation': ('application/pdf', '.pdf')}

def download(client, file):
    mime, name = file['mimeType'], file['name']
    if mime in EXPORTS:
        mime, ext = EXPORTS[mime]
        req = client.files().export_media(fileId=file['id'], mimeType=mime)
        name += ext
    elif mime.startswith('application/vnd.google-apps.'):
        raise ValueError('Formato nativo nao suportado')
    else:
        req = client.files().get_media(fileId=file['id'])
    data = io.BytesIO()
    downloader = MediaIoBaseDownload(data, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    data.seek(0)
    return name, mime, data

@app.get('/')
@protect
def index(): return render_template('index.html')

@app.get('/api/origem')
@protect
def origem():
    etapa = 'autenticacao'

    try:
        print("[GOOGLE V3] Iniciando listagem")

        client = drive()

        etapa = 'listagem'
        files = list_source(client)

        print(f"[GOOGLE] Arquivos encontrados: {len(files)}")

        return jsonify(files)

    except Exception as e:
        app.logger.error(
            "GOOGLE V3 | Etapa: %s | Erro: %s | Errno: %s",
            etapa,
            type(e).__name__,
            getattr(e, 'errno', None)
        )

        return jsonify(
            error='Falha ao listar origem. Confira os logs.'
        ), 502
# @app.get('/api/origem')
# @protect
# def origem():
#     try: return jsonify(list_source(drive()))
#     except Exception as e:
#         app.logger.error('Erro origem: %s', type(e).__name__)
#         return jsonify(error='Falha ao listar origem. Confira configuracao e permissoes.'), 502

@app.get('/api/destino')
@protect
def destino():
    try: return jsonify(list_destination(container()))
    except Exception as e:
        app.logger.error('Erro destino: %s', type(e).__name__)
        return jsonify(error='Falha ao listar destino. Confira o conteiner e as credenciais.'), 502

@app.post('/api/migrar')
@protect
def migrar():
    if request.headers.get('X-CloudTransfer') != '1': return jsonify(error='Requisicao invalida'), 403
    try:
        source, target = drive(), container()
        files = list_source(source)
        results = []
        for file in files:
            name = file['name']
            try:
                name, mime, data = download(source, file)
                with data:
                    target.upload_blob(name=name, data=data, overwrite=False, content_settings=ContentSettings(content_type=mime))
                status, message = 'sucesso', 'Arquivo copiado'
            except ResourceExistsError:
                status, message = 'erro', 'Arquivo ja existe; preservado no destino'
            except Exception as e:
                status, message = 'erro', 'Falha na transferencia: ' + type(e).__name__
            app.logger.info('%s | %s | %s', status.upper(), name, message)
            results.append({'name':name,'status':status,'message':message})
        return jsonify(results=results)
    except Exception as e:
        app.logger.error('Erro migracao: %s', type(e).__name__)
        return jsonify(error='Nao foi possivel iniciar a migracao.'), 502

if __name__ == '__main__':

    print("[INFO] Iniciando CloudTransfer...")

    try:
        print("[INFO] Conectando ao Azure Blob Storage...")

        container()

        print("[SUCESSO] Azure configurado corretamente.")

    except Exception as e:
        print(f"[ERRO] Falha ao configurar Azure: {e}")

    app.run(
        port=int(os.getenv('PORT', '5000'))
    )