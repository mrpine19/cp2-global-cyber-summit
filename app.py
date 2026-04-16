from flask import Flask, render_template, request, flash, redirect, url_for

app = Flask(__name__)
app.secret_key = 'super_secret_key'

@app.route('/')
def index():
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
