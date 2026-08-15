# Codex_Readme.md

## Specifica completa del progetto

## DNS Switcher Pro

Applicazione desktop Windows con backend sviluppato in Python e frontend realizzato come webapp moderna di ultima generazione, elegante, professionale, veloce e semplice da utilizzare, destinata all'uso personale di Alex Lignola.

Python deve essere utilizzato esclusivamente per il backend, la logica applicativa, l'accesso al router, il database, la gestione sicura delle credenziali e l'esecuzione dei comandi Windows. L'interfaccia utente non deve essere costruita con toolkit grafici Python tradizionali: deve essere una vera webapp frontend basata su tecnologie web moderne.

L'applicazione deve permettere di cambiare rapidamente il DNS IPv4 distribuito dal router TIM tra:

- server Pi-hole installato sul server ZimaOS;
- DNS standard del router TIM.

Il router TIM utilizzato attualmente ha indirizzo `192.168.1.1`, il server ZimaOS con Pi-hole ha indirizzo `192.168.1.2` e il firmware visualizzato è `AGTHP_2.4.5`. Gli indirizzi devono essere modificabili dalle impostazioni e non devono essere considerati valori fissi nel codice.

Copyright 2026 Alex Lignola  
Created by Alex Lignola

---

## 1. Obiettivo dell'applicazione

Il router TIM permette di configurare un solo indirizzo nel campo `Server DNS`. L'app deve quindi alternare il valore del campo tra:

```text
DNS Pi-hole:      192.168.1.2
DNS Standard:     192.168.1.1
```

L'utente deve poter premere un pulsante per applicare immediatamente una delle due modalità.

L'app deve:

1. collegarsi al pannello web del router;
2. autenticarsi utilizzando le credenziali salvate localmente;
3. modificare il campo DNS della rete LAN/DHCP;
4. salvare e applicare la configurazione;
5. eseguire i comandi di aggiornamento DNS su Windows;
6. mostrare tutti i passaggi nel terminale integrato;
7. verificare che il cambio sia stato applicato correttamente;
8. mostrare chiaramente la modalità attiva.

L'architettura deve separare nettamente backend e frontend:

- backend Python con API locali;
- frontend webapp in React e TypeScript;
- comunicazione tramite REST API e WebSocket;
- esecuzione desktop su Windows tramite Microsoft Edge WebView2, usando `pywebview` come contenitore dell'applicazione;
- nessuna esposizione del backend sulla rete LAN: il servizio deve ascoltare esclusivamente su `127.0.0.1`.

Non inserire mai i due indirizzi in forma `192.168.1.2/192.168.1.1`: il router TIM dispone di un solo campo DNS IPv4.

---

## 2. Pulsanti principali

La schermata principale deve contenere due pulsanti grandi, ben visibili e coerenti graficamente.

### Pulsante DNS Pi-Hole

Testo:

```text
Switch Mode DNS Pi-Hole
```

Funzioni:

- usa l'indirizzo configurato nel campo `IP server Pi-hole`;
- verifica che il server sia raggiungibile;
- modifica il DNS del router;
- applica la configurazione;
- rinnova la configurazione DHCP del computer;
- svuota la cache DNS di Windows;
- verifica che le query siano indirizzate al server Pi-hole;
- aggiorna lo stato grafico dell'app.

Colore consigliato: verde/viola o altro colore associato alla modalità Pi-hole.

### Pulsante DNS Standard

Testo:

```text
Switch Mode DNS Standard
```

Funzioni:

- usa l'indirizzo configurato nel campo `IP router DNS Standard`;
- modifica il DNS del router;
- applica la configurazione;
- rinnova la configurazione DHCP del computer;
- svuota la cache DNS di Windows;
- verifica il nuovo DNS;
- aggiorna lo stato grafico dell'app.

Colore consigliato: blu/grigio o altro colore associato alla modalità standard.

### Stato modalità attiva

La webapp deve mostrare sempre:

- modalità attiva: `DNS Pi-hole`, `DNS Standard` oppure `Stato sconosciuto`;
- indirizzo DNS attualmente configurato;
- ultimo cambio effettuato;
- risultato dell'ultima verifica;
- data e ora dell'ultima operazione;
- eventuali errori o avvisi.

Durante un'operazione i pulsanti devono essere disabilitati per evitare richieste duplicate.

---

## 3. Impostazioni modificabili

Creare una schermata `Impostazioni` raggiungibile dal menu o da un pulsante con icona a ingranaggio.

### Indirizzi IP

I due indirizzi devono essere modificabili dall'utente:

```text
IP router DNS Standard: 192.168.1.1
IP server Pi-hole:      192.168.1.2
```

Requisiti:

- usare campi con validazione IPv4;
- impedire il salvataggio di indirizzi non validi;
- mostrare un messaggio chiaro in caso di errore;
- fornire un pulsante `Testa connessione` per ciascun indirizzo;
- salvare i valori nel database locale;
- non hardcodare gli indirizzi nei moduli operativi;
- permettere il ripristino dei valori predefiniti.

### Router

Impostazioni modificabili:

- indirizzo IP del router;
- porta HTTP/HTTPS;
- protocollo HTTP o HTTPS;
- timeout connessione;
- timeout applicazione configurazione;
- eventuale modalità compatibilità router TIM.

Valore predefinito dell'indirizzo router:

```text
192.168.1.1
```

### Credenziali router

L'app deve permettere di modificare:

- nome utente amministratore;
- password amministratore.

La password deve essere mostrata inizialmente come campo nascosto con possibilità di visualizzazione temporanea tramite icona.

Non chiedere mai all'utente di inserire le credenziali in chat, nei file del progetto o nei log.

### Comandi Windows

Nelle impostazioni deve essere possibile scegliere il livello di aggiornamento:

#### Aggiornamento rapido

```text
ipconfig /flushdns
ipconfig /renew
ipconfig /flushdns
```

#### Aggiornamento completo

```text
ipconfig /release
ipconfig /renew
ipconfig /flushdns
```

L'utente deve poter abilitare o disabilitare l'aggiornamento completo. Il comando `/release` può interrompere temporaneamente la connettività, quindi deve essere accompagnato da un avviso.

---

## 4. Database locale

Utilizzare SQLite per un piccolo database locale.

Il database deve essere salvato esclusivamente in:

```text
Codex_Work/data/dns_switcher.db
```

Il database non deve essere incluso nel repository GitHub.

### Tabelle suggerite

#### `settings`

Campi suggeriti:

- `key`;
- `value`;
- `updated_at`.

Chiavi minime:

- `router_ip`;
- `router_port`;
- `router_protocol`;
- `pihole_ip`;
- `standard_dns_ip`;
- `refresh_mode`;
- `theme`;
- `last_mode`.

#### `router_credentials`

Campi suggeriti:

- `id`;
- `username`;
- `encrypted_password`;
- `created_at`;
- `updated_at`.

La password non deve essere salvata in chiaro. Su Windows utilizzare preferibilmente Windows Credential Manager tramite `keyring` oppure Windows DPAPI tramite `pywin32`. Nel database può essere memorizzato un riferimento sicuro o il valore cifrato, mai la password in formato leggibile.

#### `operation_history`

Campi suggeriti:

- `id`;
- `mode`;
- `dns_ip`;
- `started_at`;
- `completed_at`;
- `status`;
- `message`.

Non memorizzare password, cookie di sessione o token di autenticazione nello storico.

---

## 5. Automazione del router TIM

Creare un modulo separato, ad esempio:

```text
backend/app/services/router_client.py
```

Il modulo deve implementare un client dedicato al router TIM.

### Requisiti tecnici

- creare una sessione HTTP persistente;
- eseguire il login al router;
- gestire cookie e token CSRF, se presenti;
- individuare il form o l'endpoint della pagina `Rete Locale → LAN`;
- modificare esclusivamente il campo `Server DNS`;
- applicare la configurazione tramite il pulsante o endpoint corretto;
- verificare la risposta del router;
- gestire timeout, sessione scaduta, credenziali errate e router non raggiungibile;
- non scrivere password, cookie o token nei log;
- non utilizzare valori fissi nei moduli di rete.

Prima di implementare l'automazione definitiva, analizzare il comportamento reale del firmware `AGTHP_2.4.5`. Se il router non espone un endpoint semplice e stabile, usare un adapter di automazione browser con Playwright come fallback, mantenendo separata questa implementazione dal resto dell'applicazione.

Struttura consigliata:

```python
class RouterClient:
    def login(self) -> bool: ...
    def get_current_dns(self) -> str | None: ...
    def set_dns(self, dns_ip: str) -> bool: ...
    def apply_configuration(self) -> bool: ...
    def logout(self) -> None: ...
```

Il codice deve verificare che l'indirizzo da inviare sia un IPv4 valido e rifiutare qualsiasi stringa contenente più indirizzi, slash o testo arbitrario.

---

## 6. Esecuzione dei comandi Windows

Creare un modulo backend separato:

```text
backend/app/services/windows_network.py
```

Usare `subprocess.Popen` o `subprocess.run` in modo asincrono e non bloccante per il backend. L'output deve essere inviato al frontend in tempo reale tramite WebSocket o Server-Sent Events.

Ogni comando deve:

- essere visualizzato nel terminale integrato;
- mostrare data e ora;
- mostrare stdout e stderr;
- mostrare il codice di uscita;
- interrompersi correttamente in caso di annullamento;
- gestire permessi insufficienti e assenza del comando;
- non bloccare il thread principale dell'interfaccia.

Comandi previsti:

```text
ipconfig /release
ipconfig /renew
ipconfig /flushdns
ipconfig /all
```

Per la verifica finale usare anche una query DNS controllata, preferibilmente con il punto finale nel dominio:

```text
nslookup google.com. <DNS_ATTIVO>
```

Non affidarsi esclusivamente all'output di `ipconfig /all`: alcuni dispositivi possono conservare il lease DHCP precedente. Mostrare all'utente un avviso se il rinnovo non è immediatamente rilevabile.

---

## 7. Terminale integrato nella webapp

Inserire nella schermata principale della webapp un terminale compatto con:

- testo monospaziato;
- sfondo scuro;
- colori distinti per comandi, output, successo, avvisi ed errori;
- autoscroll configurabile;
- pulsante `Cancella`;
- pulsante `Copia log`;
- pulsante `Salva log`;
- possibilità di ridimensionamento;
- limite massimo di righe per evitare consumo eccessivo di memoria.

Il terminale deve ricevere gli eventi dal backend in tempo reale tramite WebSocket. Il frontend non deve eseguire direttamente comandi di sistema e non deve avere accesso diretto a password o credenziali del router.

Esempio di output:

```text
[08:45:10] Modalità richiesta: DNS Pi-hole
[08:45:10] Verifica server Pi-hole: 192.168.1.2
[08:45:10] Server raggiungibile sulla porta DNS 53
[08:45:11] Connessione al router 192.168.1.1
[08:45:12] Login router completato
[08:45:12] DNS precedente: 192.168.1.1
[08:45:12] Impostazione nuovo DNS: 192.168.1.2
[08:45:13] Configurazione router applicata
[08:45:13] Esecuzione: ipconfig /renew
[08:45:15] Esecuzione: ipconfig /flushdns
[08:45:16] Verifica completata: DNS Pi-hole attivo
```

Non mostrare mai la password o dati sensibili nel terminale.

---

## 8. Frontend webapp di ultima generazione

L'interfaccia deve essere sviluppata come webapp moderna e non con PySide6, Tkinter, CustomTkinter o altri toolkit grafici Python tradizionali.

### Stack frontend richiesto

Usare preferibilmente:

- React;
- TypeScript con modalità strict;
- Vite per sviluppo e build;
- Tailwind CSS per il design system;
- shadcn/ui e Radix UI per componenti accessibili e professionali;
- Lucide Icons per le icone;
- Framer Motion per animazioni leggere e fluide;
- TanStack Query per richieste API, cache e gestione dello stato server;
- Zustand, se necessario, per lo stato locale dell'interfaccia;
- React Hook Form e Zod per form, validazione e impostazioni;
- WebSocket per terminale, log e avanzamento in tempo reale.

Non aggiungere dipendenze inutili o sovrapposte. Usare versioni stabili e compatibili, verificando la documentazione ufficiale durante lo sviluppo.

### Contenitore desktop

La webapp deve essere visualizzata come applicazione desktop tramite `pywebview`, utilizzando Microsoft Edge WebView2 su Windows 11. Non deve aprirsi obbligatoriamente come scheda del browser.

In modalità sviluppo deve essere possibile usare il server Vite. In produzione il backend Python deve servire gli asset statici compilati del frontend dalla cartella `frontend/dist`.

### Prestazioni

La webapp deve essere veloce e reattiva:

- caricamento iniziale rapido;
- build frontend ottimizzata e minificata;
- code splitting quando utile;
- aggiornamenti mirati senza rendering inutili;
- operazioni di rete e comandi Windows eseguiti dal backend senza bloccare l'interfaccia;
- feedback immediato durante login, cambio DNS e rinnovo DHCP;
- animazioni brevi che non rallentino l'uso;
- nessuna dipendenza remota necessaria durante l'esecuzione dell'app compilata.

Caratteristiche richieste:

- finestra ridimensionabile;
- design moderno e pulito;
- modalità chiara;
- modalità scura;
- modalità automatica in base al tema di Windows, se supportata;
- pulsanti grandi con icone;
- effetti hover e pressed;
- card per lo stato DNS;
- colori coerenti per Pi-hole, DNS standard, successo e errore;
- layout utilizzabile anche con risoluzioni ridotte;
- font leggibili;
- tooltip esplicativi;
- messaggi comprensibili anche a utenti non tecnici.

Aspetto visivo richiesto:

- stile premium e professionale;
- dashboard a card con gerarchia visiva chiara;
- gradienti delicati, ombre leggere e bordi moderni;
- design coerente con Windows 11;
- badge di stato e indicatori animati;
- notifiche toast non invasive;
- transizioni fluide tra dashboard e impostazioni;
- responsive design per diverse dimensioni della finestra;
- accessibilità da tastiera, focus visibile e contrasto adeguato;
- nessun aspetto da pagina HTML grezza o da pannello amministrativo generico.

Layout consigliato:

```text
┌───────────────────────────────────────────────┐
│ DNS Switcher Pro                 ⚙ Impostazioni│
├───────────────────────────────────────────────┤
│ Stato attuale: DNS Pi-hole                    │
│ DNS configurato: 192.168.1.2                  │
│ Router: 192.168.1.1                           │
├──────────────────────┬────────────────────────┤
│ DNS Pi-Hole           │ DNS Standard           │
│ [Attiva Pi-hole]      │ [Attiva Standard]      │
├──────────────────────┴────────────────────────┤
│ Terminale                                      │
│ [output operazioni...]                         │
├───────────────────────────────────────────────┤
│ Verifica DNS   Copia log   Cancella   Esci     │
└───────────────────────────────────────────────┘
```

---

## 9. Avvisi IPv6

Il router TIM può continuare ad annunciare un DNS IPv6 locale, ad esempio un indirizzo `fe80::...`, anche quando l'IPv6 Internet risulta disabilitato. In questo caso alcuni dispositivi possono bypassare il DNS IPv4 di Pi-hole.

L'app deve quindi mostrare nella schermata impostazioni un avviso informativo:

```text
Attenzione: alcuni dispositivi potrebbero utilizzare il DNS IPv6 del router TIM e bypassare Pi-hole. Il cambio eseguito da questa app riguarda il DNS IPv4 distribuito dal DHCP del router.
```

Prevedere un test opzionale della configurazione IPv6 e indicare chiaramente che l'app non deve modificare impostazioni IPv6 senza una funzione specifica e verificata.

---

## 10. Architettura del progetto

Struttura consigliata:

```text
dns-switcher-pro/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── routes_dns.py
│   │   │   ├── routes_settings.py
│   │   │   ├── routes_status.py
│   │   │   └── websocket_terminal.py
│   │   ├── config/
│   │   │   ├── defaults.py
│   │   │   └── settings_manager.py
│   │   ├── database/
│   │   │   ├── connection.py
│   │   │   ├── models.py
│   │   │   └── repositories.py
│   │   ├── services/
│   │   │   ├── router_client.py
│   │   │   ├── timhub_client.py
│   │   │   ├── windows_network.py
│   │   │   ├── dns_verifier.py
│   │   │   └── operation_manager.py
│   │   ├── security/
│   │   │   ├── credential_store.py
│   │   │   └── secret_masking.py
│   │   └── utils/
│   │       ├── logging_config.py
│   │       ├── validators.py
│   │       └── version.py
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── dns-switcher/
│   │   │   ├── settings/
│   │   │   ├── status/
│   │   │   └── terminal/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── services/
│   │   ├── stores/
│   │   ├── styles/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.ts
├── desktop/
│   ├── launcher.py
│   └── webview_manager.py
├── tests/
│   ├── backend/
│   └── frontend/
├── assets/
├── docs/
├── Codex_Work/
│   ├── data/
│   ├── logs/
│   ├── venv/
│   ├── npm-cache/
│   ├── cache/
│   ├── builds/
│   └── temp/
├── GeneraExe.py
├── DNSSwitcherPro.spec
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── pyproject.toml
```

Tutti i file di sviluppo, database locali, log, cache, venv, build, test temporanei e configurazioni personali devono rimanere in `Codex_Work/` e la cartella deve essere esclusa integralmente da Git.

### Backend Python

Usare Python 3.12 o superiore con FastAPI e Uvicorn. Il backend deve fornire API REST tipizzate e un canale WebSocket per terminale e avanzamento. Deve gestire router, SQLite, credenziali, comandi Windows e verifiche DNS.

### Frontend webapp

Il frontend deve contenere esclusivamente presentazione e interazione utente. Non deve eseguire comandi Windows, leggere il database SQLite o conoscere la password del router. Tutte le operazioni sensibili devono passare attraverso API locali protette del backend.

### Comunicazione locale sicura

- bind esclusivo su `127.0.0.1`;
- porta locale scelta in modo sicuro e gestita dal launcher;
- token di sessione temporaneo tra WebView e backend;
- CORS ristretto all'origine locale prevista;
- nessuna API esposta sulla LAN;
- nessun dato sensibile inserito negli asset statici del frontend.

---

## 11. Sicurezza e privacy

Obblighi:

- non inserire password reali nel codice;
- non inserire password reali in `README.md`, `Codex_Readme.md` o nei test;
- non creare un `.env` reale nel repository;
- distribuire solo `.env.example` con valori fittizi;
- non salvare password in chiaro nel database;
- non mostrare password nei log;
- non stampare cookie o token di sessione;
- non inviare dati fuori dalla rete locale;
- non aprire porte sul router;
- non modificare firewall o port forwarding;
- chiedere conferma prima di azioni potenzialmente distruttive;
- gestire correttamente logout e chiusura sessione.

La password deve poter essere cambiata dalla schermata impostazioni senza dover ricreare il database.

---

## 12. Gestione errori

Gestire almeno questi casi:

- router spento o irraggiungibile;
- Pi-hole spento;
- IP router non valido;
- IP Pi-hole non valido;
- porta 53 non raggiungibile;
- credenziali router errate;
- sessione router scaduta;
- endpoint del firmware non disponibile;
- errore durante il salvataggio del router;
- timeout HTTP;
- errore durante `ipconfig`;
- mancati privilegi Windows;
- rete temporaneamente non disponibile dopo `/release`;
- DNS IPv6 del router ancora attivo;
- configurazione applicata ma lease DHCP non ancora rinnovato.

Ogni errore deve avere:

- messaggio comprensibile;
- dettaglio tecnico nel terminale;
- suggerimento operativo;
- stato finale coerente;
- possibilità di riprovare.

---

## 13. Test richiesti

Creare test automatici per:

- validazione degli indirizzi IPv4;
- salvataggio e lettura delle impostazioni;
- cifratura e recupero delle credenziali;
- selezione della modalità Pi-hole;
- selezione della modalità standard;
- esecuzione simulata dei comandi Windows;
- gestione di stdout e stderr;
- risposta router positiva;
- credenziali errate;
- timeout router;
- Pi-hole non raggiungibile;
- verifica DNS positiva e negativa;
- database non disponibile;
- log senza password o token;
- persistenza del tema e dell'ultima modalità.

Usare mock e fixture per i test di rete. I test non devono contattare il router reale e non devono contenere credenziali personali.

---

## 14. Packaging e avvio

Preparare:

- ambiente virtuale Python;
- Node.js LTS esclusivamente per sviluppo e compilazione del frontend;
- `requirements.txt` o `pyproject.toml` aggiornato;
- `package.json` e lockfile aggiornati;
- script di avvio per sviluppo;
- script di build Windows;
- file `.spec` per PyInstaller;
- versione eseguibile `.exe` per Windows 10 e Windows 11;
- icona applicazione;
- eventuale installer separato;
- compilazione preventiva della webapp tramite Vite;
- inclusione degli asset `frontend/dist` nell'eseguibile;
- avvio tramite `pywebview` e Microsoft Edge WebView2;
- avvio senza finestra console, dato che il terminale applicativo è integrato nella webapp;
- guida per l'installazione delle dipendenze;
- guida per l'avvio in modalità sviluppo.

Il database personale deve essere creato al primo avvio dentro `Codex_Work/data/` oppure nella cartella dati utente dell'applicazione, mai nella root pubblica del repository.

### File GeneraExe.py obbligatorio

Al termine dello sviluppo Codex deve creare nella root del progetto un file denominato esattamente:

```text
GeneraExe.py
```

Lo script deve permettere di generare l'eseguibile Windows con un solo comando:

```powershell
python GeneraExe.py
```

`GeneraExe.py` deve:

1. verificare che l'esecuzione avvenga su Windows;
2. verificare Python 3.12 o superiore;
3. verificare la disponibilità di Node.js e npm;
4. verificare o installare le dipendenze di build mancanti con conferma chiara;
5. eseguire i test essenziali prima della compilazione;
6. compilare il frontend React/TypeScript con Vite;
7. verificare che `frontend/dist` sia stato creato correttamente;
8. generare o utilizzare il file PyInstaller `.spec`;
9. includere backend, frontend compilato, icone e asset necessari;
10. includere correttamente `pywebview` e il supporto WebView2;
11. generare un'app senza finestra console esterna;
12. produrre il file eseguibile nella cartella `dist/`;
13. mostrare nel terminale percorso, dimensione e risultato della build;
14. restituire un codice di uscita diverso da zero in caso di errore;
15. non includere database personali, password, `.env`, log o contenuti di `Codex_Work/`.

Output finale richiesto:

```text
dist/DNSSwitcherPro.exe
```

L'eseguibile deve funzionare su Windows 11 senza richiedere l'installazione separata di Python o Node.js. Microsoft Edge WebView2 Runtime può essere considerato un prerequisito di sistema e deve essere controllato all'avvio con un messaggio chiaro se non disponibile.

---

## 15. File README.md reale dell'applicazione

Codex deve creare un file `README.md` reale, completo e pronto per GitHub, con:

- nome e descrizione dell'app;
- screenshot o spazio predisposto per screenshot;
- badge iniziali;
- caratteristiche principali;
- requisiti;
- installazione;
- configurazione iniziale;
- utilizzo dei due pulsanti;
- impostazioni IP router e Pi-hole;
- gestione delle credenziali;
- comportamento del rinnovo DHCP;
- avviso sul DNS IPv6 TIM;
- struttura del progetto;
- descrizione dell'architettura backend Python + frontend webapp React/TypeScript;
- tecnologie frontend utilizzate;
- sviluppo e test;
- packaging Windows;
- utilizzo del comando `python GeneraExe.py`;
- percorso finale `dist/DNSSwitcherPro.exe`;
- troubleshooting;
- sicurezza;
- licenza;
- copyright e autore.

Usare questi badge in formato Markdown valido:

```markdown
![Versione](https://img.shields.io/badge/versione-1.1.0-6858e8)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4)
![Python](https://img.shields.io/badge/Python-%E2%89%A53.12-3776AB)
![Licenza](https://img.shields.io/badge/licenza-GPL--3.0-545b68)
```

Nel README inserire chiaramente:

```text
Copyright 2026 Alex Lignola
Created by Alex Lignola
```

Il README non deve contenere password, indirizzi IP personali eventualmente diversi dai valori di esempio, token o altre credenziali reali.

---

## 16. File LICENSE

Creare nella root del progetto un file denominato esattamente:

```text
LICENSE
```

Il file deve contenere il testo originale integrale della:

```text
GNU GENERAL PUBLIC LICENSE
Version 3, 29 June 2007
```

Utilizzare il testo ufficiale GPL-3.0, senza abbreviazioni, traduzioni o modifiche, reperibile dalla fonte ufficiale GNU/GitHub. Il progetto deve essere distribuito con licenza GPL-3.0.

Nel README indicare:

```text
Questo progetto è distribuito secondo i termini della GNU General Public License v3.0. Consultare il file LICENSE per il testo completo della licenza.
```

Il copyright del progetto deve essere riportato nei file principali e nel README:

```text
Copyright 2026 Alex Lignola
Created by Alex Lignola
```

Verificare le licenze di tutte le dipendenze utilizzate e documentarle nel README o in `THIRD_PARTY_NOTICES.md` quando necessario.

---

## 17. File `.gitignore`

Il file `.gitignore` deve escludere almeno:

```gitignore
Codex_Work/
.env
.env.*
!.env.example
*.db
*.sqlite
*.sqlite3
*.log
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
venv/
build/
dist/
node_modules/
frontend/dist/
*.spec.bak
```

Non pubblicare mai:

- password;
- token GitHub;
- chiavi API;
- credenziali database;
- certificati;
- chiavi private;
- cookie del router;
- database personale;
- file `.env` contenenti dati reali;
- log personali;
- ambienti virtuali;
- cache e build locali.

---

## 18. Piano di sviluppo

### Fase 1 - Analisi

- verificare il firmware reale del TIM HUB;
- identificare login, form e endpoint della pagina LAN/DHCP;
- verificare la modifica manuale del campo DNS;
- verificare il comportamento del router dopo il salvataggio;
- documentare eventuali limiti del firmware.

### Fase 2 - Base applicativa

- creare la struttura separata backend Python e frontend webapp;
- creare il database SQLite;
- implementare gestione impostazioni;
- implementare gestione sicura delle credenziali;
- creare logging interno;
- creare le API locali FastAPI;
- creare il canale WebSocket per terminale e avanzamento.

### Fase 3 - Automazione router

- implementare login;
- leggere DNS attuale;
- modificare DNS;
- applicare la configurazione;
- verificare il risultato;
- gestire errori e timeout.

### Fase 4 - Comandi Windows

- implementare esecuzione asincrona;
- collegare l'output al terminale della webapp tramite WebSocket;
- aggiungere modalità rapida e completa;
- implementare verifica con `nslookup`.

### Fase 5 - Frontend webapp

- configurare React, TypeScript, Vite e Tailwind CSS;
- creare il design system e i componenti riutilizzabili;
- creare dashboard professionale;
- creare i due pulsanti principali;
- creare stato modalità;
- creare terminale integrato;
- creare impostazioni;
- aggiungere tema chiaro/scuro;
- aggiungere avvisi e conferme;
- integrare REST API e WebSocket;
- ottimizzare prestazioni, accessibilità e responsive design;
- integrare la webapp nel contenitore desktop `pywebview`.

### Fase 6 - Test e packaging

- eseguire test automatici;
- verificare login e cambio DNS su router reale;
- verificare Pi-hole acceso e spento;
- verificare rinnovo DHCP;
- verificare Windows 10 e Windows 11;
- creare e verificare `GeneraExe.py`;
- generare `dist/DNSSwitcherPro.exe`;
- aggiornare README e LICENSE;
- controllare che nessun dato personale finisca nel repository.

---

## 19. Criteri di completamento

Il progetto è completo solo quando:

- la webapp frontend è realmente utilizzabile, moderna e non è un semplice prototipo;
- Python è utilizzato come backend e non come toolkit grafico;
- frontend e backend sono separati e comunicano tramite API locali;
- il terminale riceve gli eventi dal backend in tempo reale;
- i due pulsanti cambiano il DNS del router;
- gli indirizzi router e Pi-hole sono modificabili;
- le credenziali possono essere cambiate dalle impostazioni;
- le credenziali non sono salvate in chiaro;
- il terminale mostra i comandi e il relativo risultato;
- i comandi Windows vengono eseguiti senza bloccare la webapp;
- il programma verifica il DNS effettivamente configurato;
- gli errori vengono gestiti senza chiudere l'app;
- il database personale è escluso da Git;
- esistono `README.md`, `LICENSE` e `.gitignore`;
- `LICENSE` contiene il testo originale integrale GPL-3.0;
- `README.md` contiene i badge richiesti e il copyright;
- esiste `GeneraExe.py` e genera correttamente `dist/DNSSwitcherPro.exe`;
- l'eseguibile funziona su Windows 11 senza installazione separata di Python o Node.js;
- il progetto è pronto per essere copiato su GitHub senza credenziali o file personali;
- viene mantenuto il riferimento:

```text
Copyright 2026 Alex Lignola
Created by Alex Lignola
```
