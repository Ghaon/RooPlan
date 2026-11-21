#ifndef ReleaseVersion
  #error ReleaseVersion is required
#endif
#ifndef BuildRoot
  #error BuildRoot is required
#endif

[Setup]
AppId=RooPlan.Desktop
AppName=RooPlan
AppVersion={#ReleaseVersion}
DefaultDirName={localappdata}\Programs\RooPlan
PrivilegesRequired=lowest
SetupArchitecture=x64
DefaultGroupName=RooPlan
DisableProgramGroupPage=auto
UninstallDisplayIcon={app}\RooPlan.exe
SetupIconFile={#BuildRoot}\RooPlan.ico
OutputDir={#BuildRoot}\release
OutputBaseFilename=RooPlan-{#ReleaseVersion}-Windows-x64-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "zhcn"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#BuildRoot}\dist\RooPlan\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\RooPlan"; Filename: "{app}\RooPlan.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\RooPlan.exe"; Description: "{cm:LaunchProgram,RooPlan}"; Flags: postinstall nowait skipifsilent unchecked
