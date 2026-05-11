# Lembretes de medicamento (Windows)

Aplicação em **Python** com **janela gráfica** para **criar, listar, editar e excluir** medicamentos. Calcula automaticamente os horários do dia a partir da **primeira toma**, do **intervalo em horas** e da **quantidade de doses por dia**, e envia **notificações nativas do Windows**. Pode ficar na **bandeja do sistema** enquanto corre em segundo plano.

## Funcionalidades

- **Novo / Editar / Excluir** medicamentos na lista.
- Campos por medicamento: **nome**, **primeira hora do dia (HH:MM)**, **intervalo entre tomas (horas)** — aceita decimais, ex.: `4,5` — e **doses por dia**.
- Coluna **Horários gerados** mostra os lembretes calculados (ex.: 08:00, 14:00, 20:00).
- **Fechar a janela** (X) **oculta** para a bandeja; use o ícone → **Abrir** ou o menu **Ficheiro**.
- Ficheiro **`config.json`** junto ao `.exe` ou ao script (gravado automaticamente ao alterar dados).
- **Modo debug**: caixa **«Debug: intervalo em minutos»** — o valor de intervalo passa a ser **minutos** entre tomas (em vez de horas), para testar notificações em pouco tempo. O título da janela e o texto do toast indicam modo de teste. Limite do intervalo: **1 a 1440 minutos**. Recomenda-se baixar **«Verificar relógio a cada»** para **5–15 s** durante os testes.

## Requisitos

- **Windows 10 ou 11**
- **Python 3.10+** (para correr o código-fonte)

## Instalação (código-fonte)

```powershell
cd c:\Users\professor\Downloads\medicamento
python -m pip install -r requirements.txt
```

**Tkinter** vem com o instalador oficial do Python no Windows; se faltar, no instalador marque *tcl/tk* ou reinstale o Python com componentes completos.

## Como executar (código-fonte)

```powershell
python medicamento_app.py
```

(`medicamento_tray.py` redireciona para a mesma aplicação.)

Para abrir **sem consola**:

```powershell
pythonw medicamento_app.py
```

## Formato do `config.json`

| Campo | Descrição |
|--------|-----------|
| `check_interval_seconds` | De quanto em quanto tempo o app consulta o relógio (5–300 s). Pode ajustar na barra da janela. |
| `debug_interval_in_minutes` | Se `true`, o campo numérico de intervalo de cada medicamento é interpretado em **minutos** (apenas para testes). |
| `medications` | Lista de medicamentos. |
| `medications[].id` | Identificador único (gerado pela app). |
| `medications[].name` | Nome do medicamento. |
| `medications[].first_time` | Primeira toma do dia, `HH:MM`. |
| `medications[].interval_hours` | Horas entre tomas (modo normal) ou **minutos** se `debug_interval_in_minutes` for `true`. |
| `medications[].doses_per_day` | Número de lembretes por dia (1–48). |

**Formato antigo** com apenas `"times": ["08:00", ...]` é **lido** e **convertido** automaticamente na primeira leitura (ficheiro é normalizado ao gravar de novo).

Exemplo:

```json
{
  "check_interval_seconds": 20,
  "debug_interval_in_minutes": false,
  "medications": [
    {
      "id": "…",
      "name": "Vitamina D",
      "first_time": "08:00",
      "interval_hours": 6,
      "doses_per_day": 3
    }
  ]
}
```

Os horários do dia são: `first_time + k × interval_hours` para `k = 0 … doses_per_day - 1` (com mudança de dia à meia-noite quando necessário).

## Executável (.exe)

Gera **`dist\MedicamentoLembretes.exe`** (sem janela de consola):

```powershell
.\build_exe.ps1
```

Ou:

```powershell
python -m pip install -r requirements.txt -r requirements-build.txt
python -m PyInstaller --clean --noconfirm medicamento_tray.spec
```

Coloque **`config.json` na mesma pasta** que o `.exe` (ou deixe a app criar um modelo na primeira execução).

> **Antivírus:** executáveis PyInstaller são por vezes analisados na primeira corrida; é habitual no Windows.

## Bandeja do sistema

- **Botão direito** no ícone: **Abrir**, **Ocultar**, **Sair**.
- **Sair** termina lembretes e fecha a aplicação.

## Notificações

Em **Configurações → Sistema → Notificações**, confirme que as notificações estão ativas para a aplicação.

## Iniciar com o Windows

Crie um atalho em `shell:startup` apontando para **`MedicamentoLembretes.exe`** (e mantenha o `config.json` na mesma pasta).

## Estrutura do projeto

```
medicamento/
├── medicamento_app.py     # Aplicação principal (GUI + lembretes)
├── medicamento_tray.py    # Entrada alternativa (chama medicamento_app)
├── medicamento_tray.spec  # Receita PyInstaller
├── build_exe.ps1
├── config.json
├── requirements.txt
├── requirements-build.txt
└── README.md
```

## Dependências

| Pacote | Função |
|--------|--------|
| [winotify](https://pypi.org/project/winotify/) | Toasts do Windows |
| [pystray](https://pypi.org/project/pystray/) | Ícone na bandeja |
| [Pillow](https://pypi.org/project/Pillow/) | Ícone da bandeja |

## Aviso

Ferramenta apenas de **lembrete**; não substitui orientação médica ou farmacêutica.
