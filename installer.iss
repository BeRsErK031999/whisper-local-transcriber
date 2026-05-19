#define MyAppName "Whisper Local App"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "OpenAI Whisper Local"
#define MyAppExeName "whisper-local-app.exe"
#define MyAppId "{{8C2A7345-8166-44A9-B9AF-4068D772102B}"
#ifndef MySourceDir
  #define MySourceDir "."
#endif
#define MyModelPath MySourceDir + "\\dist\\models\\small.pt"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#MySourceDir}\installer-output
OutputBaseFilename=whisper-local-app-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"

[Files]
Source: "{#MySourceDir}\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyModelPath}"; DestDir: "{app}\models"; Flags: ignoreversion
Source: "{#MySourceDir}\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\audio_in"
Name: "{app}\text_out"
Name: "{app}\models"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent
