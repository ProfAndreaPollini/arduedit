# Manuale utente di ArduEdit

ArduEdit è un editor essenziale per scrivere sketch Arduino, verificarli e
caricarli su una scheda. L'interfaccia è pensata per concentrarsi sul codice e
sulle operazioni fondamentali di laboratorio.

## 1. Scaricare e avviare il programma

1. Apri la pagina [Releases di ArduEdit](https://github.com/OWNER/arduedit/releases).
   Prima della pubblicazione, sostituisci `OWNER` con il nome dell'account o
   dell'organizzazione GitHub del progetto.
2. Scegli la release desiderata e leggi le note, in particolare i sistemi
   supportati e le eventuali istruzioni specifiche.
3. Scarica il pacchetto adatto al tuo sistema operativo. Se è un archivio,
   estrailo e avvia il programma indicato nelle note della release.

Le release sono il riferimento per scaricare le versioni pronte all'uso.
Conserva una copia dei progetti prima di aggiornare il programma.

## 2. Preparare scheda e toolchain

Collega la scheda al computer con un cavo USB che supporti il trasferimento
dati. Se il computer non la rileva, potrebbe essere necessario installare il
driver USB del produttore della scheda.

Le schede disponibili dipendono dai core Arduino installati:

1. Dal menu **Strumenti**, apri **Gestione toolchain…**.
2. Nella scheda **Installati** puoi controllare i core presenti e aggiornare
   l'elenco.
3. Nella scheda **Installa**, scegli il core adatto alla scheda. Sono proposti
   Arduino AVR (per esempio Uno e Nano), ESP32, ESP8266 e Arduino SAMD.
4. Se la rete della scuola richiede un proxy, abilita **Usa proxy per il
   download** e inserisci i dati forniti dall'amministratore di rete.
5. Attendi il messaggio di completamento. ArduEdit aggiorna l'elenco delle
   schede dopo l'installazione.

L'installazione dei core richiede una connessione di rete. Se ArduEdit segnala
che `arduino-cli` non è disponibile, le funzioni di compilazione, caricamento,
ricerca delle librerie e monitor seriale non possono essere utilizzate: verifica
che il pacchetto distribuito sia completo o chiedi supporto a chi gestisce
l'installazione.

## 3. Creare o aprire un progetto

All'avvio puoi scegliere **Nuovo progetto** o **Apri progetto esistente**. Le
stesse azioni sono disponibili nel menu **File**.

### Creare un progetto

1. Seleziona **File > Nuovo progetto…** (oppure il pulsante nella schermata
   iniziale).
2. Inserisci il nome del progetto.
3. Scegli la cartella in cui salvarlo.
4. ArduEdit crea una nuova cartella e uno sketch iniziale
   `<NomeProgetto>.ino`, con le funzioni `setup()` e `loop()`.

La cartella del progetto non deve già esistere. Il nome diventa anche il nome
del file `.ino` principale.

### Aprire un progetto esistente

Scegli **File > Apri progetto…** e seleziona la cartella che contiene il file
`.ino` principale con lo stesso nome della cartella. Per esempio, la cartella
`Semaforo` deve contenere `Semaforo.ino`.

La schermata iniziale e il menu **File > Progetti recenti** mostrano i progetti
aperti di recente. Per aprirne uno dalla schermata iniziale, fai doppio clic
sulla voce.

## 4. Scrivere e salvare il codice

Scrivi lo sketch nell'area centrale. L'editor evidenzia alcune parole chiave,
commenti e stringhe; mostra inoltre la posizione del cursore nella barra in
basso. I suggerimenti per le API Arduino compaiono mentre digiti. Premi
**Ctrl+Spazio** per aprire i suggerimenti manualmente.

Salva con **File > Salva** o **Ctrl+S**. Le modifiche non salvate sono indicate
da un asterisco nel titolo della finestra. Prima di compilare o caricare, ArduEdit
salva automaticamente lo sketch. Se chiudi o cambi progetto con modifiche
pendenti, puoi scegliere se salvarle, scartarle o annullare l'operazione.

Ogni progetto ha un solo sketch principale modificabile nell'editor. Le librerie
del progetto, se presenti, vengono conservate nella sottocartella `libraries`.

## 5. Selezionare scheda e porta

Con un progetto aperto, usa la barra in alto:

1. Scegli la scheda dal menu **Scheda**. L'elenco dipende dai core installati.
2. Scegli la porta seriale associata alla scheda dal menu **Porta**.
3. Se hai collegato la scheda dopo aver aperto il progetto o non compare
   nell'elenco, premi **⟳** per aggiornare le porte.

Quando riesce a riconoscere il modello collegato, ArduEdit può selezionare
automaticamente la scheda corrispondente. Se rileva una differenza tra la scheda
selezionata e quella collegata, mostra un avviso prima del caricamento:
controlla la scelta prima di proseguire.

## 6. Verificare e caricare lo sketch

### Verifica

Premi **Verifica** per compilare lo sketch senza trasferirlo alla scheda. La
scheda selezionata deve essere disponibile, ma non è necessario selezionare una
porta. L'output e gli eventuali errori appaiono nella scheda **Console**.

Se l'errore segnala un header mancante, ArduEdit può proporre di aprire il
pannello **Librerie**.

### Caricamento

Premi **Carica** per compilare e trasferire lo sketch sulla scheda. Prima di
procedere, controlla che siano selezionate la scheda e la porta corrette. Durante
l'operazione il pulsante **Annulla** permette di interrompere il processo. La
console mostra l'avanzamento e l'esito.

## 7. Leggere l'output con il monitor seriale

Il monitor seriale mostra i messaggi inviati dallo sketch, per esempio con
`Serial.print()` o `Serial.println()`.

1. Seleziona la porta della scheda e premi **Monitor**.
2. Imposta il baud rate uguale a quello usato nello sketch, per esempio
   `Serial.begin(9600)`. Sono disponibili 9600, 19200, 38400, 57600 e 115200.
3. Facoltativamente, abilita **Timestamp** o inserisci testo nel campo
   **Filtra…** per mostrare solo le righe che lo contengono.
4. Premi **Pulisci** per svuotare la visualizzazione.
5. Premi **Chiudi monitor** per liberare la porta prima di caricare un nuovo
   sketch o utilizzare un altro programma.

Il monitor attuale è di sola ricezione. Il pulsante **Registra** è visibile
nell'interfaccia, ma la registrazione su file non è ancora implementata.

## 8. Gestire le librerie

Le librerie installate da ArduEdit vengono aggiunte alla cartella
`libraries` del progetto, così sono disponibili durante la compilazione di quel
progetto.

1. Apri un progetto e premi **Librerie**.
2. Per installare una libreria dall'indice Arduino, premi **Cerca nell'indice…**,
   inserisci un nome o un autore, seleziona un risultato e scegli
   **Installa nel progetto**. Questa ricerca richiede `arduino-cli` e una
   connessione di rete.
3. In alternativa, premi **Aggiungi da ZIP…** e seleziona l'archivio della
   libreria.
4. La tabella mostra le librerie presenti nel progetto. Per rimuoverne una,
   selezionala e premi **Rimuovi selezionata**; conferma solo se sei sicuro,
   perché la rimozione non può essere annullata.
5. **Apri cartella** apre la cartella `libraries` del progetto.

## 9. Risoluzione dei problemi

| Problema | Controlli da fare |
| --- | --- |
| Non compare alcuna scheda nell'elenco **Scheda** | Apri **Strumenti > Gestione toolchain…** e installa il core adatto al modello. |
| La porta non compare | Controlla il cavo USB dati, il collegamento e l'eventuale driver; poi premi **⟳**. |
| Il caricamento avvisa che la scheda potrebbe essere diversa | Verifica il modello fisico e la voce **Scheda**. Non proseguire se non sei certo della selezione. |
| La compilazione segnala un file `.h` mancante | Aggiungi la libreria richiesta da **Librerie** e verifica che sia disponibile nel progetto. |
| Il monitor non mostra testo leggibile | Imposta lo stesso baud rate di `Serial.begin(...)` nello sketch e nel monitor. |
| La porta è occupata o il caricamento non parte | Chiudi il monitor seriale e altri programmi che potrebbero usare la stessa porta, quindi riprova. |
| Non sono disponibili compilazione e upload | Verifica che `arduino-cli` sia incluso o configurato nell'installazione fornita. |

Se il problema persiste, annota il messaggio completo della **Console**, la
scheda selezionata e il sistema operativo e riportali a chi gestisce ArduEdit.
