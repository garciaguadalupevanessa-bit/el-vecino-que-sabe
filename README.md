# 🌾 El vecino que sabe

> **Tu experto en ayudas y subvenciones para agricultura y ganadería.**  
> *Se ha leído el BOE para que lo entiendas.*

---

🌐 **[Español](#español)** | 🇬🇧 **[English](#english)**

---

<a name="español"></a>
## 🇪🇸 Español

### 📝 Resumen Ejecutivo
**El vecino que sabe** (anteriormente conocido como AgroAyudas) es un agente conversacional de Inteligencia Artificial diseñado para ayudar a agricultores y ganaderos de España a identificar, evaluar y tramitar las ayudas y subvenciones públicas (PAC, estatales y autonómicas) a las que tienen derecho.

Traduce el perfil técnico y operativo de una explotación agraria o ganadera en búsquedas deterministas sobre una base de datos verificada, evaluando los requisitos legales sin inventar información y citando siempre las fuentes oficiales.

### 🎯 Problema y Solución
- **El Problema:** Las ayudas públicas están dispersas en múltiples boletines oficiales (BOE, BDNS, FEGA), redactadas en un lenguaje administrativo complejo y con trámites digitales farragosos. Muchos productores pierden subvenciones por falta de información o dependencia de terceros.
- **La Solución:** Un asistente inteligente con *function calling* determinista que analiza la elegibilidad del productor, explica los requisitos faltantes, indica cómo solicitarlas y sugiere alternativas.

### 🌟 Alineación con los ODS
- **ODS 8:** Trabajo decente y crecimiento económico (fortalecimiento del sector primario rural).
- **ODS 10:** Reducción de las desigualdades (democratización del acceso a información administrativa).
- **ODS 17:** Alianzas para lograr los objetivos (Tech for Inclusion Challenge - Ebury & Somos F5).

### 🛠️ Arquitectura Técnica
El proyecto se estructura como un monorepo modular:
- **Backend:** Python 3.11, FastAPI, Pydantic v2, Uvicorn, API OpenAI/Groq (LLM con *function calling* determinista), PostgreSQL (psycopg 3).
- **Frontend:** React 18, Vite, Nginx.
- **Infraestructura:** Docker & Docker Compose.

text
el-vecino-que-sabe/
├── backend/          # API REST con FastAPI, agente y herramientas deterministas
├── frontend/         # Interfaz de usuario en React + Vite
├── docker-compose.yml # Orquestación de servicios (App + DB)
└── .gitignore        # Reglas de exclusión de Git

### 🚀 Instalación y Ejecución Local

1. **Clonar el repositorio:**
bash
git clone https://github.com/garciaguadalupevanessa-bit/el-vecino-que-sabe.git
cd el-vecino-que-sabe

2. **Backend (FastAPI):**
bash
python -m venv .venv

En Windows PowerShell:
..venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload

3. **Frontend (React):**

bash
cd frontend
npm install
npm run dev

---

<a name="english"></a>
## 🇬🇧 English

### 📝 Executive Summary
**El vecino que sabe** (*The Neighbor Who Knows*) is an AI conversational agent designed to help farmers and livestock owners in Spain easily find, evaluate, and apply for public grants and subsidies (CAP, national, and regional).

It translates a farm’s operational profile into deterministic queries against a verified database, evaluating eligibility criteria without inventing facts and always providing official source citations.

### 🎯 Problem & Solution
- **The Problem:** Public grants are scattered across various official bulletins (BOE, BDNS, FEGA), written in complex bureaucratic jargon, and involve complicated digital procedures. Many farmers miss out on funds due to lack of accessible information.
- **The Solution:** An intelligent assistant with deterministic function calling that evaluates eligibility, explains missing requirements, provides application step-by-step guides, and offers alternatives.

### 🌟 Sustainable Development Goals (SDGs)
- **SDG 8:** Decent Work and Economic Growth.
- **SDG 10:** Reduced Inequalities.
- **SDG 17:** Partnerships for the Goals (Tech for Inclusion Challenge - Ebury & Somos F5).

### 🛠️ Technical Stack
- **Backend:** Python 3.11, FastAPI, Pydantic v2, Uvicorn, OpenAI/Groq API (LLM function calling), PostgreSQL.
- **Frontend:** React 18, Vite, Nginx.
- **DevOps:** Docker & Docker Compose.
