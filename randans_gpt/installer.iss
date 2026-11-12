; Inno Setup script (https://jrsoftware.org/isinfo.php) - builds Output\RandansGPT-Setup.exe
; 1) run build_exe.bat   2) open this file in Inno Setup   3) press Compile
#define AppName "Randan's GPT"
#define AppVersion "1.0"
#define AppExe "RandansGPT.exe"

[Setup]
AppId={{B7C1E3A2-6D0A-4E55-9B7B-RANDANSGPT01}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Randan
DefaultDirName={autopf}\RandansGPT
DefaultGroupName={#AppName}
OutputBaseFilename=RandansGPT-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
; Optional: sign the installer (see PUBLISHING.md)  SignTool=signtool

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
{ Friendly reminder if the free Microsoft Edge WebView2 runtime is missing (it is preinstalled on Windows 11). }
function WebView2Installed(): Boolean;
var v: String;
begin
  Result := RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v)
         or RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v);
end;
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not WebView2Installed()) then
    MsgBox('Randan''s GPT needs the free "Microsoft Edge WebView2 Runtime".' + #13#10 +
           'Download it from https://developer.microsoft.com/microsoft-edge/webview2/ and run the installer, then start the app.',
           mbInformation, MB_OK);
end;
