import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, flash, redirect, url_for
import oracledb
import re

load_dotenv()

bloco_plsql = r'''
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
    usr = os.getenv("DB_USER")
    psw = os.getenv("DB_PASSWORD")
    dns = os.getenv("DB_DSN")

    return oracledb.connect(user=usr, password=psw, dsn=dns)

def faz_consulta_banco():
    pending_registrations = []
    audit_logs = []
    try:
        with obter_conexao() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    u.id, 
                    u.nome, 
                    u.email, 
                    u.trust_score, 
                    i.status,
                    i.id as inscricao_id
                FROM 
                    usuarios u
                JOIN 
                    inscricoes i ON u.id = i.usuario_id
                WHERE 
                    i.status = 'PENDING'
            """)
            for row in cursor:
                pending_registrations.append({
                    "id": row[5],
                    "name": row[1],
                    "email": row[2],
                    "trust_score": row[3],
                    "status": row[4],
                    "inscricao_id": row[5]
                })

            cursor.execute("""
                SELECT 
                    id, 
                    inscricao_id, 
                    motivo, 
                    data
                FROM 
                    log_auditoria
                ORDER BY 
                    data DESC
            """)
            for row in cursor:
                audit_logs.append({
                    "id": row[0],
                    "inscricao_id": row[1],
                    "motivo": row[2],
                    "data": row[3].strftime("%Y-%m-%d %H:%M:%S")
                })
            
            cursor.close()

    except oracledb.Error as e:
        print(f"Erro do banco de dados: {e}")
    except Exception as ex:
        print(f"Ocorreu um erro inesperado: {ex}")
    
    return pending_registrations, audit_logs

app = Flask(__name__)
app.secret_key = 'super_secret_key'

@app.route('/')
def index():
    pending_registrations, audit_logs = faz_consulta_banco()
    
    return render_template('index.html', registrations=pending_registrations, logs=audit_logs)

@app.route('/run_audit', methods=['POST'])
def run_audit():
    try:
        with obter_conexao() as conn:
            cursor = conn.cursor()
            cursor.execute(bloco_plsql)
            conn.commit()
            flash('Varredura automática executada com sucesso! Todos os e-mails suspeitos foram bloqueados e Trust Scores reduzidos.', 'success')
    except oracledb.Error as e:
        flash(f'Erro ao executar varredura automática: {e}', 'error')
        print(f"Erro ao executar bloco PL/SQL: {e}")
    except Exception as ex:
        flash(f'Ocorreu um erro inesperado durante a varredura automática: {ex}', 'error')
        print(f"Erro inesperado: {ex}")
    
    return redirect(url_for('index'))

@app.route('/run_audit_id', methods=['POST'])
def run_audit_id():
    reg_id = request.form.get('reg_id')
    if reg_id:
        try:
            with obter_conexao() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        u.id, 
                        u.email,
                        i.id
                    FROM 
                        usuarios u
                    JOIN 
                        inscricoes i ON u.id = i.usuario_id
                    WHERE 
                        i.id = :reg_id
                """, reg_id=reg_id)
                
                result = cursor.fetchone()
                
                if result:
                    user_id, user_email, inscricao_id = result
                    
                    email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
                    is_valid = re.match(email_pattern, user_email)
                    is_fake = '@fake.com' in user_email
                    is_temp = '@temp-mail.org' in user_email

                    if not is_valid or is_fake or is_temp:

                        cursor.execute("""
                            UPDATE usuarios 
                            SET trust_score = trust_score - 15 
                            WHERE id = :user_id
                        """, user_id=user_id)

                        cursor.execute("""
                            UPDATE inscricoes 
                            SET status = 'CANCELLED' 
                            WHERE id = :inscricao_id
                        """, inscricao_id=inscricao_id)

                        cursor.execute("""
                            INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO) 
                            VALUES (:inscricao_id, 'E-mail fraudulento ou malformado detectado (varredura individual).')
                        """, inscricao_id=inscricao_id)
                        
                        conn.commit()
                        flash(f'Varredura INDIVIDUAL executada com sucesso para a Inscrição ID #{reg_id}. E-mail suspeito detectado e ação tomada.', 'info')
                    else:
                        flash(f'Varredura INDIVIDUAL executada para a Inscrição ID #{reg_id}. Nenhum problema detectado.', 'info')
                else:
                    flash(f'Inscrição com ID #{reg_id} não encontrada.', 'error')
                
                cursor.close()
        except oracledb.Error as e:
            flash(f'Erro ao executar varredura individual: {e}', 'error')
            print(f"Erro ao executar varredura individual: {e}")
        except Exception as ex:
            flash(f'Ocorreu um erro inesperado durante a varredura individual: {ex}', 'error')
            print(f"Erro inesperado: {ex}")
    else:
        flash('Por favor, forneça um ID válido para a varredura.', 'error')
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
