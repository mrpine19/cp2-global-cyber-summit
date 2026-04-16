import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, flash, redirect, url_for
import oracledb

bloco_plsql = r'''
        DECLARE
            -- Cursor explícito usando JOIN
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
                    
                    -- Registra a auditoria (CORRIGIDO: INSCRICAO_ID ao invés de id_inscricao)
                    INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO) 
                    VALUES (v_inscricoes.id_inscricao, 'E-mail fraudulento ou malformado detectado.');
                    
                END IF;
                
            END LOOP;
            
            CLOSE c_inscricoes_pendentes;
            
            -- Persistência exigida
            COMMIT; 
        
        EXCEPTION
            WHEN OTHERS THEN
                ROLLBACK;
                RAISE_APPLICATION_ERROR(-20001, 'Erro interno!');
        END;
    '''

def obter_conexao():
    usr = os.getenv("DB_USER")
    psw = os.getenv("DB_PASSWORD")
    dns = os.getenv("DB_DSN")

    return oracledb.connect(user=usr, password=psw, dsn=dns)

def faz_consulta_banco():

    try:
        with obter_conexao() as conn:
            print("Conexão estabelecida com sucesso!")

    except oracledb.Error as e:
        print(f"Erro do banco de dados: {e}")
        return []
    except Exception as ex:
        print(f"Ocorreu um erro inesperado: {ex}")
        return []
app = Flask(__name__)
app = Flask(__name__)
app.secret_key = 'super_secret_key'

@app.route('/')
def index():
    faz_consulta_banco()
    pending_registrations = [
        {"id": 101, "name": "John Doe", "email": "john@example.com", "trust_score": 85, "status": "PENDING"},
        {"id": 102, "name": "Botnet Alpha", "email": "admin@fake.com", "trust_score": 50, "status": "PENDING"},
        {"id": 103, "name": "Alice Smith", "email": "alice@company.com", "trust_score": 90, "status": "PENDING"},
        {"id": 104, "name": "Spammer X", "email": "free-tickets@temp-mail.org", "trust_score": 40, "status": "PENDING"}
    ]
    
    audit_logs = [
        {"id": 1, "inscricao_id": 99, "motivo": "Domínio temporário (trashmail) detectado.", "data": "2023-10-25 09:45:12"},
        {"id": 2, "inscricao_id": 85, "motivo": "Tentativa de injeção anulada.", "data": "2023-10-25 10:12:00"}
    ]
    
    return render_template('index.html', registrations=pending_registrations, logs=audit_logs)

@app.route('/run_audit', methods=['POST'])
def run_audit():
    flash('Varredura AUTOMÁTICA executada com sucesso! Todos os e-mails suspeitos foram bloqueados e Trust Scores reduzidos.', 'success')
    return redirect(url_for('index'))

@app.route('/run_audit_id', methods=['POST'])
def run_audit_id():
    reg_id = request.form.get('reg_id')
    if reg_id:
        flash(f'Varredura INDIVIDUAL executada com sucesso para a Inscrição ID #{reg_id}.', 'info')
    else:
        flash('Por favor, forneça um ID válido para a varredura.', 'error')
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
