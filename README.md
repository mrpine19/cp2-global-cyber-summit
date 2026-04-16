# SOC Dashboard - Global Cyber Summit

Este projeto é um painel (dashboard) desenvolvido em **Python/Flask** e **Banco de Dados Oracle** para o Security Operations Center (SOC) do evento *Global Cyber Summit*. O objetivo principal da aplicação é monitorar o cadastro de usuários e proteger o sistema contra inscrições feitas por botnets ou usuários mal-intencionados, utilizando técnicas de auditoria e validação de e-mails em banco de dados através de blocos PL/SQL e rotinas Python.

## Funcionalidades Principais

*   **Listagem de Inscrições:** Visualização de todas as inscrições pendentes (`PENDING`) ou já verificadas (`VERIFIED`) juntamente com o *Trust Score* do usuário.
*   **Varredura Automática (Em Lote):** Um bloco PL/SQL é acionado via sistema para iterar sobre todas as inscrições pendentes, procurando por padrões de e-mails inválidos, malformados ou pertencentes a domínios de descarte (`@fake.com`, `@temp-mail.org`).
    *   **Ação para fraudes:** Se uma fraude for detectada, a inscrição é cancelada (`CANCELLED`), o usuário perde 15 pontos de *Trust Score* e a ação é registrada na tabela `LOG_AUDITORIA`.
    *   **Ação para inscrições válidas:** Se o e-mail for válido, a inscrição é alterada para `VERIFIED`.
*   **Varredura Individual:** O administrador pode fornecer o ID de uma inscrição específica. O sistema aplica a mesma lógica de validação de fraude descrita acima apenas para aquele usuário.
*   **Adição de Usuários:** Interface para cadastro rápido de usuários, já inserindo automaticamente o registro nas tabelas `USUARIOS` e `INSCRICOES` usando as *Triggers* e *Sequences* do Oracle.
*   **Histórico de Auditoria:** Painel dedicado à exibição cronológica das ações de auditoria (fraudes detectadas) do sistema.

## Modelagem de Dados (DDL)

O projeto depende da seguinte estrutura de tabelas, sequências e gatilhos no banco de dados Oracle:

### Tabelas

*   **`USUARIOS`**
    *   `ID` (PK): Identificador do usuário.
    *   `NOME`: Nome completo.
    *   `EMAIL` (UNIQUE): E-mail do usuário.
    *   `PRIORIDADE`: Nível de prioridade (1 a 3).
    *   `SALDO`: Saldo financeiro (default 0).
    *   `TRUST_SCORE`: Pontuação de confiança (default 100).
*   **`INSCRICOES`**
    *   `ID` (PK): Identificador da inscrição.
    *   `USUARIO_ID` (FK): Referência ao usuário.
    *   `STATUS`: Estado da inscrição (`PENDING`, `CANCELLED` ou `VERIFIED`).
    *   `VALOR_PAGO`: Valor pago.
    *   `TIPO`: Tipo da inscrição.
*   **`LOG_AUDITORIA`**
    *   `ID` (PK): Identificador do log.
    *   `INSCRICAO_ID` (FK): Referência à inscrição auditada.
    *   `MOTIVO`: Descrição do problema/fraude.
    *   `DATA`: Data e hora do evento.

### Sequências e Triggers
O banco faz o uso de **Sequences** (`SEQ_USUARIOS`, `SEQ_INSCRICOES`, `SEQ_LOG_AUDITORIA`) em conjunto com **Triggers** de `BEFORE INSERT` para realizar o preenchimento automático das chaves primárias (Auto Increment) nas três tabelas principais do sistema.

## Pré-requisitos e Execução

### Dependências

*   Python 3.x
*   Flask (`pip install flask`)
*   Oracle DB Driver (`pip install oracledb`)
*   Python-dotenv (`pip install python-dotenv`)

### Configurando o Ambiente

Crie um arquivo `.env` na raiz do projeto contendo suas credenciais do banco de dados Oracle:

```env
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_DSN=host:porta/servico
SECRET_KEY=sua_chave_secreta_do_flask
```

### Rodando o Projeto

1.  Garanta que o DDL foi executado corretamente no seu banco Oracle.
2.  Inicie o servidor Flask:
    ```bash
    python app.py
    ```
3.  Acesse o sistema no navegador através de `http://localhost:5000` (ou a porta informada pelo Flask).
