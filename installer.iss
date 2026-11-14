; Build after build.ps1 with Inno Setup 7 (ISCC.exe installer.iss).
#ifndef PayloadDir
  #define PayloadDir SourcePath + "dist\MovieBox"
#endif
#ifndef ReleaseDir
  #define ReleaseDir SourcePath + "dist\installer"
#endif
#ifndef SetupIdentity
  #define SetupIdentity "MovieBoxDesktop-EmranHossain"
#endif

[Setup]
AppId={#SetupIdentity}
AppName=MovieBox
AppVersion=0.10.0
AppPublisher=Emran Hossain
AppPublisherURL=https://github.com/emransm877/moviebox-desktop
AppSupportURL=https://github.com/emransm877/moviebox-desktop/issues
AppUpdatesURL=https://github.com/emransm877/moviebox-desktop/releases
DefaultDirName={localappdata}\Programs\MovieBox Desktop
DefaultGroupName=MovieBox
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#ReleaseDir}
OutputBaseFilename=MovieBox-Setup-0.10.0-windows-x64
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\MovieBox.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
Uninstallable=yes
VersionInfoDescription=MovieBox Setup
VersionInfoProductName=MovieBox
VersionInfoVersion=0.10.0.0

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MovieBox"; Filename: "{app}\MovieBox.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\MovieBox"; Filename: "{app}\MovieBox.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\MovieBox.exe"; Description: "Open MovieBox"; Flags: nowait postinstall skipifsilent

; Library/history remain in LOCALAPPDATA\MovieBoxDesktop, outside {app}.
; Never delete that directory during uninstall.
