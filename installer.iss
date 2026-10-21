[Setup]
AppName=YAVIS
AppVersion=0.1.0
DefaultDirName={autopf}\YAVIS
DefaultGroupName=YAVIS
OutputDir=installer_out
OutputBaseFilename=YAVIS-Setup
PrivilegesRequired=lowest
Compression=lzma2
SolidCompression=yes

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknuepfung erstellen"
Name: "autostart"; Description: "YAVIS mit Windows starten"; Flags: unchecked

[Files]
Source: "dist\YAVIS\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\YAVIS"; Filename: "{app}\YAVIS.exe"
Name: "{autodesktop}\YAVIS"; Filename: "{app}\YAVIS.exe"; Tasks: desktopicon
Name: "{userstartup}\YAVIS"; Filename: "{app}\YAVIS.exe"; Tasks: autostart

[Run]
Filename: "{app}\YAVIS.exe"; Description: "YAVIS starten"; Flags: nowait postinstall skipifsilent
