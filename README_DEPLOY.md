# Deploy do Sistema Web BNB

Stack: Flask + SQLite + arquivos em `uploads/`.

## Comandos de deploy

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
gunicorn app:app
```

## Variáveis de ambiente recomendadas

```env
SECRET_KEY=troque-por-uma-chave-grande-e-segura
AUTH_ENABLED=1
FLASK_DEBUG=0
```

Se usar disco persistente:

```env
DATABASE_PATH=/var/data/database.db
UPLOAD_DIR=/var/data/uploads
```

## Acesso inicial

Login: `testebnb`
Senha: `bnb123`

Troque a senha no código antes de usar com dados reais.
