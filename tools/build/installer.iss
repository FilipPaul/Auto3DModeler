; Inno Setup 6 script: the installer of the one-folder build (docs/DISTRIBUTION.md).
; tools/build/build.py runs it when ISCC.exe is there:
;   ISCC /DAppVersion=0.9.0 /DSourceDir=<repo>\dist\Auto3DModeler /O<repo>\dist tools\build\installer.iss
; Per user, no admin by default (%LOCALAPPDATA%\Programs\Auto3DModeler); "for all users" can be chosen in the dialog.
; The user's data (%LOCALAPPDATA%\Auto3DModeler: projects, library, logs) is not in the install folder and stays
; after an uninstall or an update.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\Auto3DModeler"
#endif
#define AppName "Auto3DModeler"
#define AppExe "Auto3DModeler.exe"

[Setup]
; (the AppId keeps updates and the uninstaller together: never change it)
AppId={{6B1E2F4A-3C7D-4E8B-9A15-2D4F6C8E0A31}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Rafiontech
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputBaseFilename={#AppName}-{#AppVersion}-setup
SetupIconFile={#SourceDir}\..\..\build\stage\auto3d.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; a running copy is closed (Restart Manager) before its files are replaced or removed
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; an update replaces the whole program folder (no files of the old version left behind)
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
