# DNS Switcher Pro per ZimaOS

Questa cartella contiene la variante container dell'applicazione. Il container
espone la dashboard web, usa Chromium headless per il pannello TIM HUB e salva
impostazioni e credenziali cifrate in `/DATA/AppData/dns-switcher-pro`.

La versione 1.1.4 aggiunge il primo accesso con creazione password, il login
obbligatorio, la pagina **Imposta Password**, il logout e la revoca delle altre
sessioni dopo il cambio password. Le API operative e il terminale WebSocket
richiedono una sessione autenticata.

## Requisiti

- ZimaOS con Docker Compose disponibile.
- ZimaOS, router TIM e Pi-hole sulla stessa LAN o comunque raggiungibili tra loro.
- Architettura `amd64`.
- Almeno 2 GB liberi durante la build; l'immagine include Chromium Playwright.

## Installazione consigliata direttamente da GitHub

Non è necessario copiare manualmente il progetto su ZimaOS. Aprire il terminale
web di ZimaOS ed eseguire un solo comando:

```sh
curl -fsSL https://raw.githubusercontent.com/AngoloInformatico/DNS-SwitcherPro/main/Docker/install-from-github.sh | sh
```

Il bootstrap scarica o aggiorna il repository GitHub nella cartella
`/DATA/AppData/dns-switcher-pro-source`, quindi avvia automaticamente
`install-zimaos.sh`. Se `git` non è disponibile, utilizza l'archivio `tar.gz`
pubblicato da GitHub tramite `curl` o `wget`.

Al termine mostra l'indirizzo completo della dashboard con il token iniziale.
Se l'utente SSH non può accedere al socket Docker, lo script si rilancia
automaticamente tramite `sudo` e può chiedere la password dell'utente ZimaOS.
La configurazione temporanea di Docker viene collocata in `/tmp`, perché la
home di root di ZimaOS è in sola lettura.

## Disinstallazione diretta da GitHub

Per rimuovere container, immagine e rete Docker mantenendo dati, configurazione,
password e log per una futura reinstallazione:

```sh
curl -fsSL https://raw.githubusercontent.com/AngoloInformatico/DNS-SwitcherPro/main/Docker/uninstall-zimaos.sh | sh
```

I dati rimangono in `/DATA/AppData/dns-switcher-pro` e i sorgenti in
`/DATA/AppData/dns-switcher-pro-source`.

Per eliminare definitivamente anche dati persistenti e sorgenti:

```sh
curl -fsSL https://raw.githubusercontent.com/AngoloInformatico/DNS-SwitcherPro/main/Docker/uninstall-zimaos.sh | sh -s -- --purge
```

> **Attenzione:** l'opzione `--purge` elimina impostazioni, password, database
> e log. Questa operazione non è reversibile.

## Installazione da una copia locale

1. Copiare **l'intero progetto**, non soltanto questa cartella, sullo ZimaOS.
2. Aprire il terminale di ZimaOS e posizionarsi nella cartella del progetto.
3. Avviare lo script tramite la shell:

   ```sh
   sh Docker/install-zimaos.sh
   ```

Lo script crea `Docker/.env`, genera un token casuale, compila l'immagine e
mostra l'indirizzo completo da aprire. Al primo accesso il token viene salvato
nel browser e rimosso dalla barra degli indirizzi. Subito dopo viene richiesto
di creare la password di accesso, che dovrà essere inserita alle aperture
successive della dashboard.

Non è obbligatorio avere Docker Compose: se ZimaOS espone soltanto il comando
`docker`, lo script costruisce e avvia automaticamente il container tramite
`docker build` e `docker run`. Se il client ZimaOS non include il plugin Buildx,
la compilazione usa temporaneamente l'immagine ufficiale `docker:28-cli`, senza
installare componenti nel sistema e senza lasciare container aggiuntivi attivi.

## Installazione manuale

```sh
cp Docker/.env.example Docker/.env
# Generare un token (lo script automatico non richiede openssl):
TOKEN="$(tr -d '-' < /proc/sys/kernel/random/uuid)$(tr -d '-' < /proc/sys/kernel/random/uuid)"
sed -i "s/CAMBIA-QUESTO-TOKEN-CON-ALMENO-32-CARATTERI/$TOKEN/" Docker/.env
cd Docker
docker compose -f docker-compose.yml up -d --build
```

Aprire quindi:

```text
http://IP-DELLO-ZIMAOS:8765/?token=IL_TOKEN_CONFIGURATO
```

Il file Compose contiene anche il blocco `x-casaos` usato da ZimaOS. Per una
prima installazione locale è comunque necessario eseguire la build dalla
cartella del progetto, perché l'immagine non è pubblicata su un registry.

## Dati persistenti

Il percorso predefinito è:

```text
/DATA/AppData/dns-switcher-pro
```

Contiene database, log e password router cifrata. Per cambiare percorso,
modificare `DNS_SWITCHER_DATA_PATH` in `Docker/.env`.

La password di accesso alla dashboard è conservata nello stesso database solo
come hash PBKDF2-SHA256 con salt casuale. Può essere modificata dalla pagina
**Imposta Password**, raggiungibile dal pulsante accanto a **Impostazioni**. Il
cambio password revoca le altre sessioni aperte.

Il token è anche la chiave usata per derivare la cifratura. Se viene cambiato,
la vecchia password non sarà più leggibile e dovrà essere reinserita dalla
pagina Impostazioni.

La dashboard usa HTTP e deve rimanere accessibile soltanto dalla LAN fidata. Il
token tecnico consente solo di raggiungere il flusso di login; le API operative
richiedono anche una sessione autenticata. Non pubblicare la porta 8765 su
Internet e non condividere il token o la password di accesso.

## Comandi utili

```sh
# Entrare nella cartella: Compose carica automaticamente .env
cd Docker

# Stato
docker compose -f docker-compose.yml ps

# Log
docker compose -f docker-compose.yml logs -f

# Aggiornamento dopo modifiche ai sorgenti
docker compose -f docker-compose.yml up -d --build

# Arresto senza cancellare i dati
docker compose -f docker-compose.yml down

# Disinstallazione locale mantenendo dati e sorgenti
sh uninstall-zimaos.sh

# Disinstallazione locale completa e irreversibile
sh uninstall-zimaos.sh --purge
```

Se ZimaOS espone il comando storico, sostituire `docker compose` con
`docker-compose`. Lo script automatico rileva autonomamente quale variante usare
e, quando Compose non è installato, usa direttamente Docker.

Con l'avvio tramite Docker standard, i comandi equivalenti più utili sono:

```sh
docker ps --filter name=dns-switcher-pro
docker logs -f dns-switcher-pro
docker restart dns-switcher-pro
docker stop dns-switcher-pro
```

## Differenza rispetto alla versione Windows

Il container modifica e verifica direttamente il DNS sul router. Non esegue
`ipconfig` sui PC della rete: ogni dispositivo riceverà il nuovo DNS al rinnovo
del proprio lease DHCP. Il pulsante di switch, i log, la verifica resolver e la
pagina Impostazioni restano disponibili.
