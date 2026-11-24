## Configuração no Windows (CMD)
1. No Google Cloud Console, crie projeto, habilite Google Drive API, crie uma Service Account e uma chave JSON (se permitido). Salve como credentials.json na raiz. Compartilhe a pasta do Drive com o client_email da conta de serviço como leitor. Copie o ID da pasta da URL.
2. No Azure, crie um contêiner privado na conta autorizada pelo professor. Use nome válido, por exemplo aluno-seunome (minúsculas e hífen; confirme com o professor a adaptação do padrão do enunciado). Obtenha a connection string autorizada. Não compartilhe chaves.
3. Abra a pasta no VS Code e execute:
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
4. Edite .env: preencha o ID da pasta, connection string, nome do contêiner e uma senha forte APP_PASSWORD. Mantenha o JSON fora do Git.
5. Execute `python app.py` e abra http://localhost:5000. Login: admin e a senha definida. Clique Listar origem, Listar destino, Migrar arquivos. Confira o console e o portal Azure. Repita para verificar que duplicatas não são sobrescritas.


