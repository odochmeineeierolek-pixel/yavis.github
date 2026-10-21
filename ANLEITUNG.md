# So bekommst du die YAVIS.exe (ohne CMD)

1. Auf github.com ein Konto anlegen und oben rechts **+ > New repository**. Name: `yavis`, **Public** waehlen
   (oeffentliche Repositories haben unbegrenzte kostenlose Build-Minuten), dann **Create repository**.
2. Auf der neuen Seite **uploading an existing file** klicken. Dieses ZIP entpacken und den **gesamten Inhalt**
   (inkl. des Ordners `.github`) ins Browserfenster ziehen. Unten **Commit changes**.
3. Pruefen, dass im Repository der Ordner `.github/workflows/build.yml` zu sehen ist. Falls nicht:
   **Add file > Create new file**, als Namen `.github/workflows/build.yml` eintippen, Inhalt aus der Datei einfuegen, Commit.
4. Oben auf **Actions** > links **Build YAVIS** > **Run workflow** > gruener Knopf. Warten (grobe Schaetzung: 10-20 Minuten).
5. **Gruener Haken:** Auf den Lauf klicken, ganz unten bei **Artifacts** `YAVIS-Windows` herunterladen und entpacken.
   Darin: `YAVIS-portable.zip` (entpacken, `YAVIS\YAVIS.exe` starten) und, falls der optionale Schritt klappte, `YAVIS-Setup.exe`.
6. **Roter Haken:** Auf den roten Schritt klicken, den Text kopieren und an Claude schicken.

Hinweise: Windows zeigt bei neuen, unsignierten Programmen "Der Computer wurde geschuetzt" -> **Weitere Informationen > Trotzdem ausfuehren**.
Fuer Antworten braucht YAVIS noch **Ollama** (ollama.com) mit geladenem Modell; Sprache braucht Piper + Stimmen in `%APPDATA%\YAVIS\piper`.
Beides ist noch NICHT automatisch eingerichtet.
