# Sistema Web - Checklist de Contratação

Aplicação Flask + SQLite criada a partir do roteiro fornecido para controle de demandas, checklist automático, anexos, validações, modelos de documentos, configurações de regras e relatório final.

## Como rodar 


```powershell
python app.py
```

Ou execute o arquivo:

```powershell
.\iniciar_sistema.bat
```

Acesse `http://127.0.0.1:5010`.

Este projeto usa a porta `5010` por padrão para não misturar com outros sistemas
Flask que estejam rodando em `http://127.0.0.1:5000`.

Para iniciar em outra porta:

```powershell
$env:PORT="5011"
python app.py
```

## Instalação em outro ambiente

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## Acesso inicial

Por padrão, o sistema entra direto no dashboard e não exibe login/saída.

Para reativar a tela de login, inicie com:

```powershell
$env:AUTH_ENABLED="1"
python app.py
```

Credenciais quando o login estiver ativo:

- Login: `testebnb`
- Senha: `bnb123`

O sistema trabalha em modo de usuário único. A tela de cadastro/listagem de usuários não fica disponível na interface.

O banco `database.db` é criado automaticamente na primeira execução. Os anexos ficam na pasta `uploads/`.
