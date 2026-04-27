# Sistema de Registro de Presença por QR Code

## Descrição

Este projeto consiste em um sistema de registro de presença automatizado utilizando QR Code, desenvolvido como atividade acadêmica para a disciplina de Sistemas Distribuídos.

A solução tem como objetivo substituir o processo tradicional de chamada manual por um modelo digital, onde a presença dos alunos é registrada por meio da leitura de um QR Code gerado para cada sessão.

O sistema foi projetado considerando conceitos fundamentais de sistemas distribuídos, como comunicação cliente-servidor, consistência de dados e escalabilidade.

---

## Objetivos

* Automatizar o processo de controle de presença em sala de aula
* Reduzir inconsistências e fraudes no registro de frequência
* Aplicar conceitos de sistemas distribuídos em um cenário prático
* Facilitar a gestão e consulta de dados de presença

---

## Funcionalidades

* Geração de QR Code para registro de presença
* Registro automático de presença via leitura do código
* Gerenciamento de usuários (administrador, professor e aluno)
* Controle de turmas e disciplinas
* Registro e consulta de frequência

---

## Tecnologias Utilizadas

* Python
* Django
* PostgreSQL

---

## Pré-requisitos

* Python 3.10 ou superior
* PostgreSQL configurado
* Git

---

## Como rodar o projeto

### 1. Clonar o repositório

```bash
git clone https://github.com/joaopinheros/Sistema-de-Registro-de-Presen-a-por-QR-CODE.git
cd Sistema-de-Registro-de-Presen-a-por-QR-CODE/FREQUENCIA_QR_PARTE1_attendance_system
```

---

### 2. Configurar ambiente

Copie o arquivo de exemplo:

```bash
cp .env.example .env
```

Edite o `.env` e configure seu banco de dados.

---

### 3. Executar setup automático

```bash
chmod +x setup.sh
./setup.sh
```

Esse script:

* cria o ambiente virtual
* instala dependências
* aplica migrações
* opcionalmente popula o banco
* configura arquivos estáticos

---

### 4. Iniciar o servidor

```bash
source .venv/bin/activate
python manage.py runserver
```

Acesse: http://127.0.0.1:8000/

---

## Autor

João Vitor Pinheiro e Leonardo Soares

---


## Licença

Projeto desenvolvido para fins acadêmicos.
