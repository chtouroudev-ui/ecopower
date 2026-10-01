Option Explicit
' Nelyio HTTPS F43.2 - explicit quote construction; no nested quote literals.
Dim sh, fso, root, ps, script, cmd, rc, q, logdir, logpath, errorText, errorNumber
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
q = Chr(34)
ps = fso.BuildPath(sh.ExpandEnvironmentStrings("%SystemRoot%"), "System32\WindowsPowerShell\v1.0\powershell.exe")
script = fso.BuildPath(root, "START_NELYIO_HTTPS.ps1")
logdir = fso.BuildPath(root, "logs")
logpath = fso.BuildPath(logdir, "https_bootstrap.log")

If Not fso.FileExists(ps) Then
    WScript.Echo "Windows PowerShell introuvable : " & ps
    WScript.Quit 40
End If
If Not fso.FileExists(script) Then
    WScript.Echo "Fichier absent : " & script & vbCrLf & "Copiez tout le correctif a cote de app.py."
    WScript.Quit 41
End If
If Not fso.FileExists(fso.BuildPath(root, "NELYIO_LAUNCHER_COMMON.ps1")) Then
    WScript.Echo "NELYIO_LAUNCHER_COMMON.ps1 absent. Copiez tout le correctif, pas seulement le VBS."
    WScript.Quit 42
End If

cmd = q & ps & q & " -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File " & q & script & q
' /check compiles this script and prints its command without starting services.
If WScript.Arguments.Named.Exists("check") Then
    WScript.Echo "Nelyio HTTPS F43.2 - lanceur VBScript charge sans erreur."
    WScript.Echo "Fichiers PowerShell presents. Aucun service demarre."
    WScript.Echo cmd
    WScript.Quit 0
End If

sh.CurrentDirectory = root
AppendLog "F43.2 - debut du lancement HTTPS"
On Error Resume Next
rc = sh.Run(cmd, 0, True)
errorNumber = Err.Number
errorText = Err.Description
Err.Clear
On Error GoTo 0
If errorNumber <> 0 Then
    AppendLog "Impossible de lancer PowerShell : " & errorText
    MsgBox "Impossible de lancer PowerShell : " & errorText & vbCrLf & "Utilisez START_NELYIO_HTTPS_DEBUG.bat.", vbExclamation, "Nelyio HTTPS"
    WScript.Quit 40
End If
AppendLog "Code retour HTTPS : " & rc
If rc <> 0 Then
    MsgBox "Le lancement HTTPS n'a pas abouti (code " & rc & ")." & vbCrLf & "Le navigateur HTTP local peut avoir ete ouvert en secours." & vbCrLf & vbCrLf & "Journal : " & root & "\logs\https_launcher.log" & vbCrLf & "Diagnostic : START_NELYIO_HTTPS_DEBUG.bat", vbExclamation, "Nelyio HTTPS"
End If
WScript.Quit rc

Sub AppendLog(ByVal message)
    Dim stream
    On Error Resume Next
    If Not fso.FolderExists(logdir) Then fso.CreateFolder logdir
    Set stream = fso.OpenTextFile(logpath, 8, True)
    If Err.Number = 0 Then
        stream.WriteLine Now & " - " & message
        stream.Close
    End If
    Err.Clear
    On Error GoTo 0
End Sub
