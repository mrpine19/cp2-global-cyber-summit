import os
import re
import oracledb
from dotenv import load_dotenv
from flask import Flask, render_template, request, flash, redirect, url_for

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret")

DOMINIOS_PROIBIDOS = ['@fake.com', '@temp-mail.org']
REGEX_EMAIL = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'

BLOCO_PLSQL_AUDIT = r'''
        DECLARE
            CURSOR c_inscricoes_pendentes IS
                SELECT 
                    i.id AS id_inscricao,
                    i.usuario_id,
                    u.email
                FROM 
                    inscricoes i
                JOIN 
                    usuarios u ON i.usuario_id = u.id
                WHERE 
                    i.status = 'PENDING'; 

            v_inscricoes c_inscricoes_pendentes%ROWTYPE;
        BEGIN
            OPEN c_inscricoes_pendentes;

            LOOP
                FETCH c_inscricoes_pendentes INTO v_inscricoes;
                EXIT WHEN c_inscricoes_pendentes%NOTFOUND;

                -- Validação de Domínios Falsos e E-mails Malformados
                IF NOT REGEXP_LIKE(v_inscricoes.email, '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$') 
                    OR v_inscricoes.email LIKE '%@fake.com' 
                    OR v_inscricoes.email LIKE '%@temp-mail.org' THEN

                    -- Reduz o Trust Score do Usuário em 15 pontos
                    UPDATE usuarios 
                    SET trust_score = trust_score - 15 
                    WHERE id = v_inscricoes.usuario_id;

                    -- Cancela a inscrição
                    UPDATE inscricoes 
                    SET status = 'CANCELLED' 
                    WHERE id = v_inscricoes.id_inscricao;

                    INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO, DATA) 
                    VALUES (v_inscricoes.id_inscricao, 'E-mail fraudulento ou malformado detectado.', SYSDATE);

                END IF;

            END LOOP;

            CLOSE c_inscricoes_pendentes;

            COMMIT; 

        EXCEPTION
            WHEN OTHERS THEN
                ROLLBACK;
                RAISE_APPLICATION_ERROR(-20001, 'Erro interno!');
        END;
    '''

def obter_conexao():
    return oracledb.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        dsn=os.getenv("DB_DSN")
    )


def is_email_fraudulento(email):
    if not re.match(REGEX_EMAIL, email):
        return True
    return any(dom in email for dom in DOMINIOS_PROIBIDOS)

@app.route('/')
def index():
    pending_registrations = []
    audit_logs = []

    try:
        with obter_conexao() as conn:
            cursor = conn.cursor()

            def make_dict_factory(cursor):
                column_names = [d[0].lower() for d in cursor.description]
                def row_factory(*args):
                    return dict(zip(column_names, args))
                return row_factory

            cursor.execute("""
                SELECT u.id, u.nome as name, u.email, u.trust_score, i.status, i.id as inscricao_id 
                FROM usuarios u 
                JOIN inscricoes i ON u.id = i.usuario_id 
                WHERE i.status = 'PENDING'
            """)

            cursor.rowfactory = make_dict_factory(cursor)
            pending_registrations = cursor.fetchall()

            cursor.execute("SELECT id, inscricao_id, motivo, data FROM log_auditoria ORDER BY data DESC")
            cursor.rowfactory = make_dict_factory(cursor)
            audit_logs = cursor.fetchall()

            for log in audit_logs:
                if log.get('data'):
                    log['data'] = log['data'].strftime("%d/%m/%Y %H:%M")

    except oracledb.Error as e:
        print(f"Erro de banco: {e}")
        flash(f"Erro de banco: {e}", "error")

    return render_template('index.html', registrations=pending_registrations, logs=audit_logs)


@app.route('/run_audit', methods=['POST'])
def run_audit():
    try:
        with obter_conexao() as conn:
            with conn.cursor() as cursor:
                cursor.execute(BLOCO_PLSQL_AUDIT, regex=REGEX_EMAIL)
            flash('Varredura em lote concluída!', 'success')
    except Exception as e:
        flash(f'Falha na auditoria: {e}', 'error')
    return redirect(url_for('index'))


@app.route('/run_audit_id', methods=['POST'])
def run_audit_id():
    reg_id = request.form.get('reg_id')
    if not reg_id:
        flash('ID inválido', 'error')
        return redirect(url_for('index'))

    try:
        with obter_conexao() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT u.id, u.email FROM usuarios u JOIN inscricoes i ON u.id = i.usuario_id WHERE i.id = :id",
                    id=reg_id)
                res = cursor.fetchone()

                if res and is_email_fraudulento(res[1]):
                    cursor.execute("UPDATE usuarios SET trust_score = trust_score - 15 WHERE id = :id", id=res[0])
                    cursor.execute("UPDATE inscricoes SET status = 'CANCELLED' WHERE id = :id", id=reg_id)
                    cursor.execute("INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO) VALUES (:id, 'Fraude Individual')",
                                   id=reg_id)
                    conn.commit()
                    flash(f'Inscrição #{reg_id} cancelada!', 'info')
                else:
                    flash(f'Inscrição #{reg_id} está limpa.', 'success')
    except Exception as e:
        flash(f'Erro: {e}', 'error')

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)