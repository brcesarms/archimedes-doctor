# 🩺 Archimedes Doctor — Gerador Autônomo de Testes com Self-Healing

> Gerador de testes unitários (`pytest`) com loop autônomo de auto-correção (*Self-Healing*). Analisa arquivos modificados via Git, extrai funções sem cobertura via AST, gera testes com o OpenCode e itera sobre o *stack trace* em ambiente isolado até os testes ficarem 100% verdes.

---

## 🎯 Como Funciona o Ciclo de Auto-Cura (Self-Healing)

```mermaid
sequenceDiagram
    autonumber
    actor Dev as 👨‍💻 Desenvolvedor
    participant Doc as 🩺 archimedes-doctor
    participant Git as 🌿 Git & AST Scanner
    participant OC as 🤖 OpenCode CLI
    participant Py as 🧪 Pytest Sandbox

    Dev->>Doc: Executa 'doctor run'
    Doc->>Git: Detecta arquivos modificados (git diff) e funções/classes
    Git-->>Doc: Lista de arquivos e alvos pendentes de teste
    Doc->>OC: Solicita geração de testes pytest para o arquivo
    OC-->>Doc: Arquivo tests/test_<nome>.py criado
    
    loop Ciclo de Auto-Cura (máx. 3-5 iterações)
        Doc->>Py: Executa pytest em ambiente isolado
        alt Testes passaram (Green)
            Py-->>Doc: Sucesso (Código 0) 🟢
            Doc-->>Dev: Paciente Curado! Relatório Verde
        else Testes falharam (Red)
            Py-->>Doc: Falha + Stack Trace cirúrgico ❌
            Doc->>OC: Envia diagnóstico + traceback para auto-correção
            OC-->>Doc: Aplica correção no código ou no teste
        end
    end
```

---

## ⚡ Principais Recursos

- 🌿 **Foco Cirúrgico em Modificações (Git Diff)**: Não perde tempo retestando o repositório inteiro; diagnostica apenas os arquivos alterados recentemente.
- 🌳 **Análise Sintática por AST**: Identifica funções síncronas, assíncronas e classes que ainda não possuem funções de teste correspondentes.
- 🩺 **Loop de Auto-Cura (Self-Healing)**: Se o teste quebrar, o `archimedes-doctor` isola o erro, captura o *stack trace* e instrui o OpenCode a corrigir a falha (seja no teste ou na implementação).
- 🛡️ **Execução Híbrida (Sandbox Local + Docker)**: Roda nativamente em subprocesso isolado com controle de `PYTHONPATH` e timeout de segurança contra loops infinitos, com suporte opcional a Docker container (`--docker`).
- 📊 **Relatórios Ricos com Rich**: Painéis de progresso, status visual de cada paciente e tabela final de cura.

---

## 🚀 Instalação e Configuração

### 1. Pré-requisitos
- Linux / macOS com Python 3.10+
- Binário do [`opencode`](https://opencode.ai) instalado no sistema

### 2. Configurar o Ambiente Local
```bash
cd ~/projetos/archimedes-doctor

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Atalhos no Terminal (`~/.local/bin`)
Os wrappers executáveis já vêm configurados:
```bash
ln -sf ~/projetos/archimedes-doctor/bin/archimedes-doctor ~/.local/bin/archimedes-doctor
ln -sf ~/projetos/archimedes-doctor/bin/doctor ~/.local/bin/doctor
```

---

## 💻 Como Usar

### 1. Curar e Testar Arquivos Modificados no Git
Basta rodar na raiz de qualquer projeto com repositório Git:
```bash
doctor run
```

### 2. Focar em um Arquivo Específico
```bash
doctor run src/modulo_critico.py --max-retries 4
```

### 3. Varredura Rápida sem Executar Testes (`scan`)
Para inspecionar quais arquivos modificados possuem funções que precisam de cobertura:
```bash
doctor scan
```

### 4. Diagnóstico de Ambiente (`info`)
Verifica se o Docker está disponível ou se o Sandbox Local será utilizado:
```bash
doctor info
```

---

## 🧪 Testes Automatizados do Próprio Projeto

```bash
PYTHONPATH=. .venv/bin/pytest -v tests/
```

---

## 🏛️ Filosofia Archimedes
Desenvolvido como parte do ecossistema de ferramentas de engenharia de software do **Archimedes Vault**.
Totalmente integrado com busca semântica local via `archimedes-rag`.
