# Evaluation Gold Standard

Mapping: ticket (customer language) -> expected article ID.
Tickets are synthetic, calibrated against real operator/layperson phrasing
from public fault descriptions. Article IDs never appear in ticket text.

## Covered tickets (retrieval eval)

| # | Ticket (customer language, DE) | Expected |
|---|---|---|
| 1  | Hallentor reagiert gar nicht, kein Brummen, keine Bewegung, gestern lief es noch | A-101 |
| 2  | Tor öffnet erst nach zwei- oder dreimaligem Drücken, beim ersten Mal nichts | A-102 |
| 3  | Tor fährt sehr langsam auf und zu, Schließen dauert ewig, Sicherheitsproblem | A-102 |
| 4  | Morgens bei Dauerbetrieb schaltet sich das Tor nach einer Weile ab, nach Pause wieder ok | A-103 |
| 5  | Schichtwechsel-Dauerbetrieb, Tor bleibt stehen, macht eine Weile nichts, dann von selbst wieder | A-103 |
| 6  | Tor fährt nicht mehr sauber in die Endstellung, mal zu früh, mal zu weit, ruckelt nach | A-104 |
| 7  | Tor zuckt beim Fahren zwischendurch, verliert kurz die Richtung, steht nicht immer gleich | A-104 |
| 8  | Nach Probealarm bleibt Brandschutztür offen, soll zufallen, hängt offen | B-401 |
| 9  | Bei Probealarm keine Reaktion, Tür bleibt offen, lässt sich nicht zum Schließen bewegen | B-401 |
| 10 | Verriegelte Tür meldet dauernd Fehler, Riegel fährt aus, System sagt nicht verriegelt | B-402 |
| 11 | Tür will nicht verriegeln, Riegel bewegt sich, Anlage zeigt nicht verriegelt an Zentrale | B-402 |
| 12 | Tür soll fürs Be-/Entladen offen bleiben, fällt aber von selbst zu, kein Alarm | B-403 |
| 13 | Offen gehaltene Tür löst sich manchmal, schließt von alleine, leichtes Anstoßen reicht | B-403 |
| 14 | Tor macht beim Fahren schrillen Ton, über Wochen lauter, sonst normal | M-301 |
| 15 | Beim Öffnen stockt das Tor immer an derselben Stelle, sonst läuft es | M-302 |
| 16 | Beim Schließen Geräusche und Ruckeln an einer Stelle, als arbeite etwas dagegen | M-302 |
| 17 | Tor wackelt leicht, ruckelt in gleichmäßigem Takt, Spalt an Schließkante ungleich | M-303 |
| 18 | An heißen Tagen geht Tor beim Schließen schwer, Motor müht sich, bei Abkühlung normal | M-304 |
| 19 | Bei Annäherung dauert Öffnen zu lange, über Wochen verschlechtert, vorher sofort | S-201 |
| 20 | Bei Annäherung öffnet Tür nur teilweise, bleibt stehen, nach und nach schlimmer, niemand dran | S-201 |
| 21 | Seit letzter Wartung erkennt Tür einen oft nicht, vorher einwandfrei, von einem Tag auf den anderen | S-202 |
| 22 | Nach Montagearbeiten öffnet Tor nur verzögert, davor nie Probleme, schlagartig | S-202 |
| 23 | Tor unterbricht beim Schließen, fährt wieder auf, nichts im Weg, unregelmäßig | S-203 |
| 24 | Tür will zugehen, öffnet wieder, kein Hindernis, häufiger bei Kälte und Nässe | S-204 |
| 25 | Tür will automatisch schließen, geht wieder auf, vor allem morgens feucht und kalt | S-204 |

## Escalation cases (no covered article -> agent must escalate, not invent)

| # | Ticket (customer language, DE) | Expected |
|---|---|---|
| E1 | Lkw ist gegen das Tor gefahren, Schloss verbogen, seitdem schließt es nicht mehr | ESCALATE |
| E2 | Nach Feuerwehreinsatz wurde Türblatt aufgebrochen, lässt sich nicht mehr schließen, reagiert nicht | ESCALATE |
| E3 | Tor lässt sich morgens nicht öffnen, rührt sich nicht, hat über Nacht gefroren | ESCALATE |