# Rowboat-Space „EHL“: Sales- und Marketing-Daten auf die PCs des Teams

**Datum:** 2026-10-10 · **Anlass:** EHL Munich 2026 Grand Finale (Demo am 11.10., 6 min Pitch)
**Status:** Entwurf zur Freigabe

## 1. Ziel

Rowboat wird zur gemeinsamen Projektübersicht des Teams. Die Daten aus den bestehenden
Deployments (Sales-Claw, Marketing) fließen automatisch in einen gemeinsamen Rowboat-Space
„EHL“. Jedes Mitglied sieht sie in der Rowboat-Desktop-App auf seinem eigenen PC.

**Erfolgskriterium:** Ein Mitglied installiert *nur* die offizielle Rowboat-Desktop-App, öffnet
einen Einladungslink, meldet sich mit E-Mail + Passwort an und sieht den Space „EHL“ mit
Übersicht, Kontakten, Versandplan, Kampagnen und Feed. Keine weitere Software (kein Tailscale,
kein Docker) auf dem PC des Mitglieds.

**Demo-Kriterium:** Ein in Sales-Claw angelegter Kontakt bzw. eine Freigabe erscheint innerhalb
von ~60 s im Feed und in den Dateien des Space auf einem zweiten Rechner außerhalb des Heimnetzes.

## 2. Ausgangslage (erkundet am 2026-10-10)

| System | Wo | Zugang | Stand |
|---|---|---|---|
| Sales-Claw (`Flissel/sales-claw`, Branch `feat/stufe-1-fundament`) | Mini-PC `vibemind-offload-1`, Tailscale `100.67.177.45` | sales-mcp `:8765` (MCP streamable-http), UI `:8791` | läuft |
| Marketing (`Flissel/vibemind-os`, `spaces/marketing`) | dieser PC | API `127.0.0.1:5510`, MCP-Sidecar `:8130` | läuft, `/api/health` ok |
| Rowboat Desktop (Upstream `rowboatlabs/rowboat`, `apps/x`) | PCs der Mitglieder | offizielle Installer | wird installiert |
| Harbor (Upstream, `apps/harbor`, Spaces-Server) | – | – | neu aufzusetzen |

Der Fork in `vibemind-os/spaces/rowboat/rowboat` (Next.js-Web-App) wird für dieses Vorhaben
**nicht** benötigt; seine Electron-App ist dort nur ein Rumpf. Wir nutzen die Upstream-Desktop-App
und den Upstream-Spaces-Server Harbor (Apache 2.0).

## 3. Entscheidungen

| # | Entscheidung | Begründung |
|---|---|---|
| E1 | Gemeinsamer Stand über Rowboat **Spaces / Harbor**, selbst gehostet auf diesem PC | Daten bleiben beim Team; Rowboat-Bordmittel statt Eigenbau |
| E2 | Harbor auf Upstream-Commit **`72e9d8c`** (2026-10-09) festgenagelt, eigene Änderungen als Patch-Dateien | Reproduzierbar, Upstream ändert sich täglich |
| E3 | **Eigener** Postgres- und GoTrue-Container im Harbor-Compose; der bestehende Supabase-Swarm bleibt unberührt | Keine Kollision mit laufenden VibeMind-Diensten |
| E4 | Login über **Supabase GoTrue `v2.188.1`** als OAuth-2.1-Server (E-Mail + Passwort) | Einziger mit Harbor getesteter Login-Server; Image liegt lokal schon vor |
| E5 | Erreichbarkeit über **Tailscale Funnel** (öffentliches HTTPS unter `https://<pc>.<tailnet>.ts.net`) | Mitglieder brauchen nur Rowboat; Desktop akzeptiert nur `https://` |
| E6 | Die **Brücke** liest nur über die vorhandenen Schnittstellen (sales-mcp, Marketing-API), nie direkt aus fremden Datenbanken | Kapselung der Fremdschemata |
| E7 | Sales: **nur der eigene Claw** (Hauptladen, Schema `sales`, sales-mcp auf dem Mini-PC). Marketing: **alle Mandanten** | Vorgabe |
| E8 | **Nur lesend Richtung Rowboat.** Kein Rückweg aus Rowboat in Sales/Marketing; Freigaben und Versand bleiben in Sales-Claw | YAGNI bis zur Demo; Freigabe-Gate bleibt erhalten |
| E9 | Keine Telefonnummern und E-Mail-Adressen von Kontakten im Space | Datensparsamkeit (DSGVO); Kontaktdaten bleiben in Sales-Claw |

## 4. Architektur

```
 Mini-PC (Tailscale)                    dieser PC                                   Internet
┌──────────────────┐     ┌───────────────────────────────────────────────┐
│ sales-mcp :8765  │◄────┤ bruecke  (Python, alle 60 s)                  │
└──────────────────┘     │   │ liest                     │ schreibt      │
┌──────────────────┐     │   ▼                           ▼ rbk_-Schlüssel│
│ Marketing :5510  │◄────┤                     harbor :4272 ──┐          │
└──────────────────┘     │                     gotrue :9999 ──┤ postgres │
                         │                                    │          │
                         │  tailscale funnel :443  → harbor   │          │      Rowboat Desktop
                         │  tailscale funnel :8443 → gotrue   │          │◄──── (Mitglied 1..n)
                         └───────────────────────────────────────────────┘
```

Alle Container binden nur an `127.0.0.1`. Nach außen gehen ausschließlich Harbor und GoTrue,
und nur über Funnel.

## 5. Komponenten

### 5.1 `harbor/` – Spaces-Server, Login, Erreichbarkeit

- `docker-compose.yml` mit drei Diensten:
  - `postgres` (`postgres:16`, Volume, zwei Datenbanken `harbor` und `auth`)
  - `gotrue` (`public.ecr.aws/supabase/gotrue:v2.188.1`, OAuth-2.1-Server-Modus mit
    dynamischer Client-Registrierung an, offene Registrierung **aus**, E-Mail-Bestätigung aus)
  - `harbor` (Build aus Upstream `72e9d8c` + `patches/`, `DATABASE_URL`, `BLOBS_DIR` auf Volume,
    `AUTH_ISSUER` = öffentliche GoTrue-Adresse, `AUTH_PUBLISHABLE_KEY` für Harbors
    Login-/Zustimmungsseite `/oauth/consent`, `HARBOR_ORG=EHL`, `HARBOR_ADDRESS` = Funnel-Adresse)
- `patches/`:
  - `0001-org-adresse-aus-env.patch`: Org-Adresse aus `HARBOR_ADDRESS` statt `localhost:<port>`
    (betrifft Einladungs- und Deep-Links).
  - `0002-keine-rowboat-seeds.patch`: kein automatisches Anlegen der Rowboat-Mitarbeiter und des
    Space „Roadboard“ im Single-Org-Pfad.
- `funnel.ps1`: richtet `tailscale funnel` für `:443 → harbor` und `:8443 → gotrue` ein.
- `mitglied-anlegen.ps1 <email> <name>`: legt das Konto über die GoTrue-Admin-API an und gibt ein
  Startpasswort aus.
- `einrichten.ps1` (einmalig, nach dem ersten Login des Admins):
  1. Space „EHL“ anlegen (`POST /v1/spaces`).
  2. Agent „Brücke“ anlegen (`POST /v1/agents`, `kind: custom`, `connection: contract`);
     `rbk_…`-Schlüssel nach `bruecke/.env` schreiben.
  3. Agent in den Space aufnehmen (`POST /v1/spaces/:id/members`, `actingMode: direct`).
  4. Einladungslink erzeugen (`POST /v1/invites`) und ausgeben.
- Das erste Admin-Mitglied wird per SQL in `member_identities` (`iss`, `sub`, `member_id`)
  eingetragen; das ist laut Upstream-Code der vorgesehene Weg im Single-Org-Pfad.

### 5.2 `bruecke/` – Synchronisation Sales/Marketing → Space

Python 3.12, Docker-Container, läuft auf diesem PC. Aufgeteilt in klar getrennte Einheiten:

| Modul | Aufgabe | Abhängigkeit |
|---|---|---|
| `quellen/sales.py` | Kontakte, Pipeline-Stufen, offene Entwürfe über sales-mcp (MCP-Client) | `SALES_MCP_URL` |
| `quellen/marketing.py` | Kampagnen, Versandaufträge, Inhalte aller Mandanten über die Marketing-API | `MARKETING_API_URL`, `MARKETING_API_KEY` |
| `modell.py` | Neutrale Datentypen (`Kontakt`, `Versand`, `Kampagne`, `Ereignis`) | – |
| `darstellung.py` | Reine Funktionen: Modell → Markdown je Datei | – |
| `ereignisse.py` | Vergleich alter/neuer Stand → neue Ereignisse | Zustandsdatei |
| `harbor.py` | Harbor-REST-Client: Datei anlegen/ändern, Feed-Nachricht posten | `HARBOR_URL`, `HARBOR_SPACE_ID`, `HARBOR_AGENT_KEY` |
| `lauf.py` | Schleife alle `INTERVALL_S` (Standard 60): lesen → darstellen → bei Änderung schreiben → Ereignisse posten | alle obigen |

**Dateien im Space „EHL“:**

| Datei | Inhalt |
|---|---|
| `Übersicht.md` | Kennzahlen: Kontakte gesamt / neu heute, Kontakte je Pipeline-Stufe, offene Freigaben, nächste 3 Versände; Zeitstempel des letzten Abgleichs |
| `Kontakte.md` | Tabelle: Name, Firma, Stufe, Quelle, angelegt am (ohne Telefon/E-Mail, E9) |
| `Versandplan.md` | Chronologisch: Termin, Kanal, Betreff/Titel, Herkunft (Marketing/Sales), Status (Entwurf / freigegeben / gesendet / abgelehnt) |
| `Kampagnen/<mandant>/<kampagne>.md` | Titel, Status, geplanter Termin, Text, Bild-Links |

**Feed-Ereignisse:** neuer Kontakt, Kontakt wechselt Pipeline-Stufe, Versand freigegeben,
Versand gesendet, Versand fehlgeschlagen. Mehrere gleichartige Ereignisse eines Laufs werden zu
einer Nachricht gebündelt („🆕 3 neue Kontakte: …“).

**Schreiblogik:**
- Jede Datei wird je Lauf vollständig neu erzeugt; ein SHA-256 des Inhalts wird mit dem zuletzt
  geschriebenen verglichen. Nur bei Abweichung wird geschrieben.
- Datei existiert noch nicht → `POST /v1/spaces/:id/assets`; sonst Version holen und
  `POST /v1/spaces/:id/changes` mit `baseVersion`. Bei Konflikt: Version neu holen, einmal
  wiederholen, sonst im nächsten Lauf.
- Gesehene Ereignis-Schlüssel stehen in `zustand.json` (Volume), damit nach einem Neustart
  nichts doppelt gepostet wird. Beim allerersten Lauf werden keine Ereignisse gepostet, nur die
  Dateien geschrieben.

## 6. Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| Quelle (sales-mcp oder Marketing-API) nicht erreichbar | Betroffene Dateien behalten den letzten Inhalt plus Kopfzeile „⚠️ Stand von HH:MM – Quelle nicht erreichbar“; keine Ereignisse aus dieser Quelle; nächster Lauf versucht es erneut |
| Harbor nicht erreichbar | Lauf wird übersprungen, Zustand nicht fortgeschrieben → nichts geht verloren |
| Schlüssel ungültig (401/403) | Klarer Log-Fehler, Container beendet sich mit Fehlercode (kein stilles Weiterlaufen) |
| Einzelner fehlerhafter Datensatz | Wird übersprungen und geloggt; der Rest der Datei wird geschrieben |

Logging über das Python-`logging`-Modul, ein Logger je Modul, kein `print`.

## 7. Sicherheit

- Container binden nur an `127.0.0.1`; öffentlich sind nur Harbor und GoTrue über Funnel.
- Harbors Dev-Modus (Anmeldung ohne `AUTH_ISSUER`) wird **nie** über Funnel betrieben. Er ist nur
  in der Entwicklung erlaubt, solange Funnel aus ist.
- GoTrue: offene Registrierung aus; Konten legt nur der Admin an.
- Geheimnisse (`rbk_`-Schlüssel, GoTrue-JWT-Secret, Service-Role-Key, Marketing-API-Key) nur in
  `.env`-Dateien, die per `.gitignore` ausgeschlossen sind; Vorlagen als `.env.example`.
- Der Brücke-Agent hat nur Mitgliedschaft im Space „EHL“.

## 8. Tests

- **Unit (`bruecke/tests/`, pytest):**
  - `darstellung`: Beispiel-Modelle → erwartetes Markdown (Snapshot), inkl. leerer Listen und
    Sonderzeichen in Namen.
  - `ereignisse`: neuer Kontakt, Stufenwechsel, Freigabe, keine Doppelmeldung nach Neustart,
    keine Meldungen im ersten Lauf.
  - `lauf`: Quelle fällt aus → Warnhinweis, letzter Inhalt bleibt; unveränderter Inhalt → kein
    Schreibaufruf (Harbor-Client gemockt).
- **Integration (lokal):** Harbor + GoTrue + Postgres per Compose; Brücke gegen Harbor mit
  Fake-Quellen; prüfen, dass Dateien und Feed-Nachrichten über die Harbor-API lesbar sind.
- **Ende-zu-Ende:** Testkontakt in Sales-Claw anlegen → binnen ~60 s in `Kontakte.md` und im Feed.
- **Mitgliederzugang:** Rowboat Desktop auf einem zweiten Rechner außerhalb des Heimnetzes
  (Handy-Hotspot): Einladungslink → Login → Space sichtbar.

## 9. Demo-Ablauf (3–4 min innerhalb des 6-min-Pitches)

1. Mitglied hat Rowboat Desktop mit Space „EHL“ offen (Übersicht, Versandplan).
2. Live in Sales-Claw einen Kontakt anlegen bzw. einen Versand freigeben.
3. Feed-Nachricht erscheint, `Übersicht.md` und `Versandplan.md` aktualisieren sich.
4. Mitglied fragt seinen Rowboat-Agenten: „Was geht diese Woche raus?“

## 10. Risiken und Rückfallebene

| Risiko | Prüfung | Rückfall |
|---|---|---|
| GoTrue `v2.188.1` hat keinen bzw. einen inkompatiblen OAuth-2.1-Server-Modus (DCR, PKCE, RFC-8414-Metadaten) | Erster Plan-Schritt, zeitbegrenzt | Neueres GoTrue-Image; sonst Rückfall unten |
| Rowboat Desktop akzeptiert keine eigene Org-Adresse oder scheitert am Login gegen unseren Server | Früh mit einem Desktop testen, sobald Harbor + GoTrue über Funnel stehen | Von Rowboat gehosteter Harbor mit Testdaten; Brücke bekommt nur andere `HARBOR_URL` |
| sales-mcp verlangt eine Anmeldung oder ist nur im Compose-Netz vorgesehen (`:8765` antwortet über Tailscale, Auth ungeprüft) | Beim Bau von `quellen/sales.py` zuerst einen Lesezugriff testen | Lesender Zugang über die vorhandene sales-claw-Konfiguration; kein Schreibzugriff |
| Funnel-Ports: nur 443, 8443, 10000 erlaubt | Zwei Dienste auf 443/8443 verteilt | – |
| Harbor-Upstream-Code ändert Annahmen der Patches | Festgenagelter Commit (E2) | – |

**Reihenfolge:** Zuerst der riskanteste Teil (GoTrue-OAuth + Harbor + Funnel + ein Desktop-Login),
parallel bzw. danach die Brücke. Die Brücke ist unabhängig vom Login testbar (Harbor im Dev-Modus
lokal ohne Funnel).

## 11. Nicht im Umfang

- Rückweg aus Rowboat nach Sales/Marketing (Termine ändern, freigeben, Kontakte anlegen).
- Synchronisation der Claws anderer Mitglieder (später über weitere `SALES_MCP_URL` möglich).
- Bilder als Dateien im Space (nur Links).
- Eigene Domain, Reverse-Proxy, Single Sign-on.
- Aufgaben-/Kanban-Objekte (Harbor kennt keine; ggf. später als Markdown-Dateien).
- Der Rowboat-Fork in `vibemind-os/spaces/rowboat`.

## 12. Vorarbeit und Lizenzen

| Teil | Herkunft | Lizenz |
|---|---|---|
| Sales-Claw | `github.com/Flissel/sales-claw` (vor dem Hackathon) | eigen |
| Marketing | `github.com/Flissel/vibemind-os`, `spaces/marketing` (vor dem Hackathon) | eigen |
| Rowboat Desktop, Harbor | `github.com/rowboatlabs/rowboat` | Apache 2.0 |
| **Neu am Hackathon** | `harbor/` (Compose, Patches, Skripte), `bruecke/` | eigen |
