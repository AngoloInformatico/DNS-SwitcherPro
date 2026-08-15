# DNS Switcher Pro per ZimaOS

Questa cartella contiene la variante container dell'applicazione. Il container
espone la dashboard web, usa Chromium headless per il pannello TIM HUB e salva
impostazioni e credenziali cifrate in `/DATA/AppData/dns-switcher-pro`.

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

## Installazione da una copia locale

1. Copiare **l'intero progetto**, non soltanto questa cartella, sullo ZimaOS.
2. Aprire il terminale di ZimaOS e posizionarsi nella cartella del progetto.
3. Avviare lo script tramite la shell:

   ```sh
   sh Docker/install-zimaos.sh
   ```

Lo script crea `Docker/.env`, genera un token casuale, compila l'immagine e
mostra l'indirizzo completo da aprire. Al primo accesso il token viene salvato
nel browser e rimosso dalla barra degli indirizzi.

## Installazione manuale

```sh
cp Docker/.env.example Docker/.env
# Generare un token (lo script automatico non richiede openssl):
TOKEN="$(tr -d '-' < /proc/sys/kernel/random/uuid)$(tr -d '-' < /proc/sys/kernel/random/uuid)"
sed -i "s/CAMBIA-QUESTO-TOKEN-CON-ALMENO-32-CARATTERI/$TOKEN/" Docker/.env
docker compose --env-file Docker/.env -f Docker/docker-compose.yml up -d --build
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

Il token è anche la chiave usata per derivare la cifratura. Se viene cambiato,
la vecchia password non sarà più leggibile e dovrà essere reinserita dalla
pagina Impostazioni.

La dashboard usa HTTP e deve rimanere accessibile soltanto dalla LAN fidata. Non
pubblicare la porta 8765 su Internet e non condividere il token.

## Comandi utili

```sh
# Stato
docker compose --env-file Docker/.env -f Docker/docker-compose.yml ps

# Log
docker compose --env-file Docker/.env -f Docker/docker-compose.yml logs -f

# Aggiornamento dopo modifiche ai sorgenti
docker compose --env-file Docker/.env -f Docker/docker-compose.yml up -d --build

# Arresto senza cancellare i dati
docker compose --env-file Docker/.env -f Docker/docker-compose.yml down
```

## Differenza rispetto alla versione Windows

Il container modifica e verifica direttamente il DNS sul router. Non esegue
`ipconfig` sui PC della rete: ogni dispositivo riceverà il nuovo DNS al rinnovo
del proprio lease DHCP. Il pulsante di switch, i log, la verifica resolver e la
pagina Impostazioni restano disponibili.
