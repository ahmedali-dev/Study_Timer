; Build with: ISCC /DAppSource=<absolute onedir output> /DOutputDir=<output> windows.iss
#ifndef AppSource
  #error AppSource must point to the generated FocusNest directory
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif
[Setup]
AppId={{84C4B552-080A-4DD4-813B-1A9CEAB37F78}
AppName=FocusNest
AppVersion=0.2.0
DefaultDirName={localappdata}\Programs\FocusNest
DefaultGroupName=FocusNest
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=FocusNest-0.2.0-Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\FocusNest.exe
SetupIconFile=..\src\assets\focusnest.ico

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\FocusNest"; Filename: "{app}\FocusNest.exe"
Name: "{autodesktop}\FocusNest"; Filename: "{app}\FocusNest.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\FocusNest.exe"; Description: "Launch FocusNest"; Flags: nowait postinstall skipifsilent

; User data is deliberately outside {app} and is never removed by this installer.
